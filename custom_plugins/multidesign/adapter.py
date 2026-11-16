"""All version-sensitive SysReptor integration lives here. See docs/PLAN.md."""
import asyncio
import uuid
from base64 import b64encode
from dataclasses import dataclass
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from sysreptor.pentests.models import PentestProject, ProjectType
from sysreptor.pentests.permissions import ProjectPermissions, ProjectTypePermissions
from sysreptor.pentests.rendering.entry import _render_pdf_task_async, format_project_template_data
from sysreptor.users.roles import Permission
from sysreptor.utils.configuration import configuration

from .compatibility import check_designs
from .models import RenderLease

MAX_RESOURCES = 64 * 1024 * 1024
MAX_DATA = 16 * 1024 * 1024
REQUEST_TIMEOUT = 360


class RenderBusy(APIException):
    status_code = 409
    default_detail = 'A render is already running for you in this project. Wait and retry.'


def project_for(user, project_id, *, write=False):
    project = get_object_or_404(PentestProject.objects.only_permitted(user).select_related('project_type'), pk=project_id)
    if not ProjectPermissions.has_read_permissions(project, user):
        raise PermissionDenied()
    if write and not ProjectPermissions.has_write_permissions(project, user, Permission.PROJECT_UPDATE_SETTINGS):
        raise PermissionDenied('Output settings require project settings permission and an editable project.')
    return project


def design_for(user, design_id):
    design = get_object_or_404(ProjectType.objects.only_permitted(user), pk=design_id)
    if not ProjectTypePermissions.has_read_permissions(design, user):
        raise PermissionDenied()
    return design


def visible_designs(user):
    # Same queryset as upstream ProjectTypeRelatedField (design selection/use).
    return ProjectType.objects.only_permitted(user).distinct().order_by('name', 'id')


def acquire_lease(project, user):
    token = uuid.uuid4()
    with transaction.atomic():
        # A project lock serializes only lease acquisition, never PDF rendering.
        PentestProject.objects.select_for_update().get(pk=project.pk)
        lease = RenderLease.objects.filter(project=project, user_id=user.id).first()
        now = timezone.now()
        if lease and lease.expires > now:
            raise RenderBusy()
        RenderLease.objects.update_or_create(project=project, user_id=user.id, defaults={
            'token': token, 'expires': now + timedelta(seconds=REQUEST_TIMEOUT + 60),
        })
    return token


def release_lease(project_id, user_id, token):
    # A late worker must never delete a replacement worker's lease.
    RenderLease.objects.filter(project_id=project_id, user_id=user_id, token=token).delete()


@dataclass(frozen=True)
class Snapshot:
    template: str
    styles: str
    data: dict
    resources: dict
    language: str
    captured_at: str


def snapshot_for(user, project_id, design_id):
    import json

    with transaction.atomic():
        if connection.vendor != 'postgresql':
            raise APIException('Multi-Design Outputs requires PostgreSQL snapshot isolation.')
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        captured_at = timezone.now().isoformat()
        # Permissions and schemas are rechecked inside the same read snapshot.
        project = project_for(user, project_id)
        design = design_for(user, design_id)
        issues = check_designs(project.project_type, design)
        if issues:
            raise ValidationError({'compatibility': issues})
        data = format_project_template_data(project=project, project_type=design)
        if len(json.dumps(data, default=str).encode()) > MAX_DATA:
            raise ValidationError('Report exceeds the 16 MiB snapshot data limit.')
        resources = {}
        total = 0
        # Capture bytes before leaving the read transaction: rendering never queries source content.
        for prefix, files in [('/assets/name/', design.assets.all()), ('/images/name/', project.images.all())]:
            for item in files:
                if prefix.startswith('/images') and not project.is_file_referenced(item, sections=True, findings=True, notes=False):
                    continue
                with item.file.open('rb') as file:
                    content = file.read(MAX_RESOURCES - total + 1)
                total += len(content)
                if total > MAX_RESOURCES:
                    raise ValidationError('Design assets and project images exceed the 64 MiB resource limit.')
                resources[prefix + item.name] = b64encode(content).decode()
        return Snapshot(design.report_template, design.report_styles, data, resources,
                        project.language, captured_at)


async def render_snapshot(snapshot):
    # Upstream dispatches to Celery (or eager async) and revokes on cancellation.
    timeout = min(REQUEST_TIMEOUT, (settings.PDF_RENDERING_TIME_LIMIT or REQUEST_TIMEOUT) + 5)
    async with asyncio.timeout(timeout):
        return await _render_pdf_task_async(
            template=snapshot.template, styles=snapshot.styles, data=snapshot.data,
            resources=snapshot.resources, language=snapshot.language, password=None,
            accessible_pdf=await configuration.aget('GENERATE_ACCESSIBLE_PDFS'),
            output=None, html=None,
        )


async def render_output(user, project_id, design_id):
    project = await sync_to_async(project_for)(user, project_id)
    # Validate visibility before acquiring a lease; snapshot validates again.
    await sync_to_async(design_for)(user, design_id)
    token = await sync_to_async(acquire_lease)(project, user)
    try:
        snapshot = await sync_to_async(snapshot_for)(user, project_id, design_id)
        result = await render_snapshot(snapshot)
        # Avoid delivering a completed render after access was revoked mid-render.
        await sync_to_async(recheck_access)(user, project_id, design_id)
        return result.to_dict() | {'snapshot_at': snapshot.captured_at}
    finally:
        await asyncio.shield(sync_to_async(release_lease)(project_id, user.id, token))


def recheck_access(user, project_id, design_id):
    # Reload role permissions as well as project/design visibility after rendering.
    current = get_object_or_404(get_user_model(), pk=user.pk)
    if not current.is_active:
        raise PermissionDenied()
    current.admin_permissions_enabled = getattr(user, 'admin_permissions_enabled', False)
    project_for(current, project_id)
    design_for(current, design_id)
