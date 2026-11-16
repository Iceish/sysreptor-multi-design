import uuid

from django.db import models


class OutputConfiguration(models.Model):
    project = models.OneToOneField('pentests.PentestProject', on_delete=models.CASCADE, primary_key=True)
    choices = models.JSONField(default=list)


class RenderLease(models.Model):
    project = models.ForeignKey('pentests.PentestProject', on_delete=models.CASCADE)
    user_id = models.UUIDField()
    token = models.UUIDField(default=uuid.uuid4)
    expires = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'user_id'], name='multidesign_project_user_lease')]
