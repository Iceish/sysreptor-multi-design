from django.http import Http404
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from sysreptor.utils.api import ViewSetAsync

from .adapter import design_for, project_for, render_output, visible_designs
from .compatibility import check_designs
from .models import OutputConfiguration
from .serializers import ConfigurationSerializer, RenderSerializer


class OutputsView(APIView):
    authentication_classes = [SessionAuthentication]
    parser_classes = [JSONParser]

    def get(self, request, project_id):
        project = project_for(request.user, project_id)
        config = OutputConfiguration.objects.filter(project=project).first()
        designs = [{
            'id': str(d.id), 'name': d.name, 'current': d.id == project.project_type_id,
            'issues': check_designs(project.project_type, d),
        } for d in visible_designs(request.user)]
        visible_ids = {d['id'] for d in designs}
        # Do not disclose names/UUIDs of designs after their visibility is revoked.
        choices = [c for c in (config.choices if config else []) if c['design_id'] in visible_ids]
        return Response({
            'project_name': project.name, 'designs': designs, 'choices': choices,
            'hidden_choices': len(config.choices if config else []) - len(choices),
            'can_configure': self.can_configure(request, project_id),
        })

    @staticmethod
    def can_configure(request, project_id):
        from rest_framework.exceptions import PermissionDenied
        try:
            project_for(request.user, project_id, write=True)
            return True
        except PermissionDenied:
            return False

    def put(self, request, project_id):
        project = project_for(request.user, project_id, write=True)
        serializer = ConfigurationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for choice in serializer.validated_data['choices']:
            design_for(request.user, choice['design_id'])
        # Serializer representation converts UUIDs to JSON-safe strings.
        OutputConfiguration.objects.update_or_create(project=project, defaults={'choices': serializer.data['choices']})
        return Response(serializer.data)


class RenderView(ViewSetAsync):
    authentication_classes = [SessionAuthentication]
    parser_classes = [JSONParser]
    throttle_scope = 'pdf'
    serializer_class = RenderSerializer

    async def create(self, request, project_id):
        serializer = await self.aget_valid_serializer(data=request.data)
        try:
            result = await render_output(request.user, project_id, serializer.validated_data['design_id'])
        except TimeoutError as exc:
            raise APIException('PDF rendering timed out. Reduce content/assets or retry; check the rendering worker.') from exc
        except (OSError, FileNotFoundError) as exc:
            raise APIException('A design asset or project image could not be read. Check storage and retry.') from exc
        except (APIException, Http404):
            raise
        except Exception as exc:
            raise APIException('PDF rendering could not finish. Retry or ask an administrator to check the rendering worker.') from exc
        response = Response(result, status=200 if result.get('pdf') else 422)
        response['Cache-Control'] = 'no-store'
        return response
