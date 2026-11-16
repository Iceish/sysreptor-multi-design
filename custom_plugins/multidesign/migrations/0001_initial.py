import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [('pentests', '0072_blindtrigramtoken_token_project_idx')]
    operations = [
        migrations.CreateModel(name='OutputConfiguration', fields=[
            ('project', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True,
                                            serialize=False, to='pentests.pentestproject')),
            ('choices', models.JSONField(default=list)),
        ]),
        migrations.CreateModel(name='RenderLease', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('user_id', models.UUIDField()),
            ('token', models.UUIDField(default=uuid.uuid4)),
            ('expires', models.DateTimeField()),
            ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='pentests.pentestproject')),
        ], options={'constraints': [models.UniqueConstraint(fields=('project', 'user_id'),
                                                            name='multidesign_project_user_lease')]}),
    ]
