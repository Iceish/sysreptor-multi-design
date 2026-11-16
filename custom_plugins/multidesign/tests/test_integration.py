import asyncio
from base64 import b64decode
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pikepdf
import pytest
from asgiref.sync import async_to_sync
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient
from sysreptor.pentests.models import PentestProject
from sysreptor.pentests.rendering.render_utils import RenderStageResult
from sysreptor.tests.mock import create_project, create_project_type, create_user

from .. import adapter
from ..adapter import RenderBusy, acquire_lease, release_lease, render_output, snapshot_for
from ..apps import MultiDesignConfig
from ..models import OutputConfiguration, RenderLease

pytestmark = pytest.mark.django_db(transaction=True)
BASE = f'/api/plugins/{MultiDesignConfig.plugin_id}/api/projects/'


@pytest.fixture
def setup():
    user = create_user(notes_kwargs=[], images_kwargs=[], files_kwargs=[])
    design = create_project_type(assets_kwargs=[])
    project = create_project(project_type=design, members=[user], notes_kwargs=[], files_kwargs=[],
                             report_data={'field_markdown': '![](/images/name/file0.png)'})
    alternate = create_project_type(assets_kwargs=[])
    client = APIClient()
    client.force_authenticate(user)
    return user, project, alternate, client


def url(project, action):
    return f'{BASE}{project.pk}/{action}/'


def source_state(project):
    project.refresh_from_db()
    return {
        'project': list(PentestProject.objects.filter(pk=project.pk).values()),
        'sections': list(project.sections.order_by('pk').values()),
        'findings': list(project.findings.order_by('pk').values()),
        'images': list(project.images.order_by('pk').values()),
        'files': list(project.files.order_by('pk').values()),
        'count': PentestProject.objects.count(),
    }


def test_anonymous_and_nonmember_cannot_read_or_render(setup):
    user, project, design, client = setup
    anon = APIClient()
    assert anon.get(url(project, 'outputs')).status_code == 403
    assert anon.post(url(project, 'render'), {'design_id': str(design.id)}, format='json').status_code == 403
    outsider = create_user(notes_kwargs=[], images_kwargs=[], files_kwargs=[])
    client.force_authenticate(outsider)
    for action in ['outputs', 'render']:
        response = client.get(url(project, action)) if action == 'outputs' else client.post(url(project, action), {'design_id': str(design.id)}, format='json')
        assert response.status_code == 404


def test_design_visibility_checked_on_get_save_and_render(setup):
    user, project, design, client = setup
    other = create_user(notes_kwargs=[], images_kwargs=[], files_kwargs=[])
    design.linked_user = other
    design.save()
    assert str(design.id) not in [d['id'] for d in client.get(url(project, 'outputs')).data['designs']]
    payload = {'choices': [{'label': 'Hidden', 'design_id': str(design.id), 'filename': 'hidden.pdf'}]}
    assert client.put(url(project, 'outputs'), payload, format='json').status_code == 404
    assert client.post(url(project, 'render'), {'design_id': str(design.id)}, format='json').status_code == 404
    assert not RenderLease.objects.exists()


def test_readonly_can_preview_but_cannot_save(setup):
    user, project, design, client = setup
    project.readonly = True
    project.save()
    assert not client.get(url(project, 'outputs')).data['can_configure']
    assert client.put(url(project, 'outputs'), {'choices': []}, format='json').status_code == 403
    before = source_state(project)
    with patch.object(adapter, 'render_snapshot', AsyncMock(return_value=RenderStageResult(pdf=b'%PDF-synthetic'))):
        response = client.post(url(project, 'render'), {'design_id': str(design.id)}, format='json')
    assert response.status_code == 200
    assert before == source_state(project)
    assert not RenderLease.objects.exists()


def test_choices_persist_and_bad_filename_rejected(setup):
    user, project, design, client = setup
    payload = {'choices': [{'label': 'Presentation', 'design_id': str(design.id), 'filename': 'slides.pdf'}]}
    assert client.put(url(project, 'outputs'), payload, format='json').status_code == 200
    assert client.get(url(project, 'outputs')).data['choices'] == payload['choices']
    payload['choices'][0]['filename'] = '../bad.pdf'
    assert client.put(url(project, 'outputs'), payload, format='json').status_code == 400


def test_csrf_session_is_enforced(setup):
    user, project, design, _ = setup
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.get(url(project, 'outputs')).status_code == 200
    # Upstream exempts JSON / non-POST requests (preflight required cross-origin).
    assert client.put(url(project, 'outputs'), {'choices': []}, format='json').status_code == 200
    assert client.post(url(project, 'render'), f'design_id={design.id}', content_type='application/x-www-form-urlencoded').status_code == 403


def test_incompatible_render_does_not_dispatch(setup):
    user, project, design, client = setup
    design.finding_fields = deepcopy(design.finding_fields) + [{'id': 'only_in_target', 'type': 'markdown', 'label': 'New'}]
    design.save()
    before = source_state(project)
    with patch.object(adapter, 'render_snapshot', AsyncMock()) as renderer:
        response = client.post(url(project, 'render'), {'design_id': str(design.id)}, format='json')
    assert response.status_code == 400
    assert 'only_in_target' in str(response.data)
    renderer.assert_not_called()
    assert before == source_state(project)
    assert not RenderLease.objects.exists()


@pytest.mark.parametrize('failure', ['snapshot', 'render', 'timeout', 'cancel', 'no_pdf'])
def test_failure_always_releases_lease_and_preserves_source(setup, failure):
    user, project, design, _ = setup
    before = source_state(project)
    snapshot_failure = OSError('synthetic missing storage object') if failure == 'snapshot' else None
    render_failure = {'render': RuntimeError('synthetic worker failure'), 'timeout': TimeoutError(),
                      'cancel': asyncio.CancelledError()}.get(failure)
    with patch.object(adapter, 'snapshot_for', side_effect=snapshot_failure, wraps=snapshot_for), \
         patch.object(adapter, 'render_snapshot', AsyncMock(side_effect=render_failure, return_value=RenderStageResult())):
        if failure == 'no_pdf':
            assert async_to_sync(render_output)(user, project.id, design.id)['pdf'] is None
        else:
            with pytest.raises((OSError, RuntimeError, TimeoutError, asyncio.CancelledError)):
                async_to_sync(render_output)(user, project.id, design.id)
    assert before == source_state(project)
    assert not RenderLease.objects.exists()


def test_expired_lease_recovery_is_scoped(setup):
    user, project, _, _ = setup
    old = acquire_lease(project, user)
    with pytest.raises(RenderBusy):
        acquire_lease(project, user)
    RenderLease.objects.update(expires=timezone.now() - timedelta(seconds=1))
    new = acquire_lease(project, user)
    release_lease(project.id, user.id, old)
    assert RenderLease.objects.get().token == new
    release_lease(project.id, user.id, new)
    assert not RenderLease.objects.exists()


def test_snapshot_isolated_from_later_edits_and_collects_images(setup):
    user, project, design, _ = setup
    snap = snapshot_for(user, project.id, design.id)
    assert '/images/name/file0.png' in snap.resources
    assert snap.data['report']['title'] == 'Report title'
    section = next(s for s in project.sections.all() if 'title' in s.data)
    section.update_data({'title': 'Later title'})
    section.save()
    assert snap.data['report']['title'] == 'Report title'
    assert snapshot_for(user, project.id, design.id).data['report']['title'] == 'Later title'
    assert not connection.in_atomic_block


def test_concurrent_users_have_independent_snapshots_and_leases(setup):
    user, project, design, _ = setup
    other = create_user(notes_kwargs=[], images_kwargs=[], files_kwargs=[])
    from sysreptor.pentests.models import ProjectMemberInfo
    ProjectMemberInfo.objects.create(project=project, user=other, roles=['pentester'])
    before = source_state(project)
    seen = []
    entered = 0

    async def concurrent():
        gate = asyncio.Event()

        async def renderer(snapshot):
            nonlocal entered
            seen.append(snapshot)
            entered += 1
            if entered == 2:
                gate.set()
            await asyncio.wait_for(gate.wait(), 10)
            return RenderStageResult(pdf=b'%PDF-concurrent')

        with patch.object(adapter, 'render_snapshot', renderer):
            return await asyncio.gather(render_output(user, project.id, design.id),
                                        render_output(other, project.id, project.project_type_id))

    results = async_to_sync(concurrent)()
    assert all(r['pdf'] for r in results)
    assert seen[0] is not seen[1] and seen[0].data is not seen[1].data
    assert before == source_state(project)
    assert not RenderLease.objects.exists()


def test_real_two_layout_pdfs_and_missing_image_warning(tmp_path):
    user = create_user(notes_kwargs=[], images_kwargs=[], files_kwargs=[])
    call_command('multidesign_demo', username=user.username, examples='/examples')
    project = PentestProject.objects.get(name='SYNTHETIC Multi-Design Demo')
    choices = OutputConfiguration.objects.get(project=project).choices
    before = source_state(project)
    sizes = []
    for choice in choices:
        response = async_to_sync(render_output)(user, project.id, choice['design_id'])
        assert response['pdf'], response['messages']
        raw = b64decode(response['pdf'])
        with pikepdf.Pdf.open(BytesIO(raw)) as pdf:
            page = pdf.pages[0]
            sizes.append((float(page.mediabox[2]), float(page.mediabox[3])))
            assert len(pdf.pages) == 3
        # Synthetic export artifacts only, optional writable mount.
        artifact = Path('/artifacts')
        if artifact.exists():
            (artifact / choice['filename']).write_bytes(raw)
    assert sizes[0][0] < sizes[0][1]
    assert sizes[1][0] / sizes[1][1] == pytest.approx(16 / 9, rel=.01)
    assert before == source_state(project)
    # Upstream renderer reports a warning for a nonexistent referenced image.
    section = project.sections.get(section_id='report')
    section.update_data({'executive_summary': '![missing](/images/name/absent.png)'})
    section.save()
    result = async_to_sync(render_output)(user, project.id, choices[0]['design_id'])
    assert any('absent.png' in str(m) for m in result['messages'])
    assert not RenderLease.objects.exists()


def test_selected_design_assets_are_frozen_and_source_assets_not_substituted(setup):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from sysreptor.pentests.models import UploadedAsset
    user, project, design, _ = setup
    UploadedAsset.objects.create(linked_object=project.project_type, name='theme.css',
                                 file=SimpleUploadedFile('theme.css', b'/* source */'))
    asset = UploadedAsset.objects.create(linked_object=design, name='theme.css',
                                          file=SimpleUploadedFile('theme.css', b'/* selected design */'))
    snap = snapshot_for(user, project.id, design.id)
    asset.delete()
    assert b64decode(snap.resources['/assets/name/theme.css']) == b'/* selected design */'


def test_resource_limit_rejects_before_dispatch_and_releases_lease(setup):
    user, project, design, _ = setup
    with patch.object(adapter, 'MAX_RESOURCES', 1):
        from rest_framework.exceptions import ValidationError
        with pytest.raises(ValidationError, match='64 MiB'):
            async_to_sync(render_output)(user, project.id, design.id)
    assert not RenderLease.objects.exists()


def test_access_revocation_during_render_blocks_result(setup):
    from asgiref.sync import sync_to_async
    from django.http import Http404
    user, project, design, _ = setup

    async def renderer(snapshot):
        await sync_to_async(project.members.all().delete)()
        return RenderStageResult(pdf=b'%PDF-not-delivered')

    with patch.object(adapter, 'render_snapshot', renderer), pytest.raises(Http404):
        async_to_sync(render_output)(user, project.id, design.id)
    assert not RenderLease.objects.exists()
