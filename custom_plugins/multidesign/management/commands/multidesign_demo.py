"""Explicit, local-only synthetic seed command; never runs at plugin startup."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from sysreptor.pentests.models import PentestFinding, PentestProject, ProjectMemberInfo, ProjectType
from sysreptor.users.models import PentestUser


class Command(BaseCommand):
    help = 'Create two compatible designs and a synthetic demo project for an existing local user.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--examples', default='/examples')

    @transaction.atomic
    def handle(self, *args, **options):
        user = PentestUser.objects.filter(username=options['username']).first()
        if not user:
            raise CommandError('Create a local user first and pass --username.')
        root = Path(options['examples'])
        schema = json.loads((root / 'schema.json').read_text())
        designs = []
        for layout, label in [('technical', 'Technical report'), ('presentation', 'Presentation')]:
            designs.append(ProjectType.objects.create(
                name=f'Multi-Design demo: {label}', language='en-US',
                report_sections=schema['report_sections'], finding_fields=schema['finding_fields'],
                report_template=(root / f'{layout}.html').read_text(),
                report_styles=(root / f'{layout}.css').read_text(),
                finding_ordering=[], finding_grouping=[],
            ))
        project = PentestProject.objects.create(name='SYNTHETIC Multi-Design Demo', project_type=designs[0], language='en-US')
        project.set_members([ProjectMemberInfo(project=project, user=user, roles=['lead'])], new=True)
        section = project.sections.get(section_id='report')
        section.update_data({
            'title': 'Synthetic ExampleCo assessment',
            'executive_summary': 'This fictional assessment found an authorization issue and outdated components. All data is synthetic.',
            'slide_summary': '- Prioritize authorization controls.\n- Schedule component updates.\n- Verify fixes with a focused retest.',
        })
        section.save()
        for order, (title, severity, summary) in enumerate([
            ('Synthetic authorization bypass', 'high', 'A fictional endpoint lacks an ownership check. Add authorization checks and retest.'),
            ('Synthetic outdated component', 'medium', 'A fictional component needs updating. Upgrade and verify compatibility.'),
        ], 1):
            finding = PentestFinding(project=project, order=order)
            finding.update_data({'title': title, 'severity': severity,
                                 'description': 'Synthetic technical detail for demonstration only. No real targets or credentials.',
                                 'recommendation': 'Apply the documented fix and retest.',
                                 'slide_summary': summary, 'include_in_presentation': True})
            finding.save()
        from ...models import OutputConfiguration
        OutputConfiguration.objects.create(project=project, choices=[
            {'label': label, 'design_id': str(design.id), 'filename': filename}
            for design, label, filename in zip(designs, ['Technical report', 'Presentation'], ['technical-report.pdf', 'presentation.pdf'])
        ])
        self.stdout.write(f'Created synthetic project {project.id}; designs {designs[0].id}, {designs[1].id}')
