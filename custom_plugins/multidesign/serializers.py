from rest_framework import serializers


class OutputChoiceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=100)
    design_id = serializers.UUIDField()
    filename = serializers.RegexField(r'^[^/\\\x00-\x1f\x7f]{1,180}\.pdf$', max_length=184)


class ConfigurationSerializer(serializers.Serializer):
    choices = OutputChoiceSerializer(many=True, max_length=20)


class RenderSerializer(serializers.Serializer):
    design_id = serializers.UUIDField()
