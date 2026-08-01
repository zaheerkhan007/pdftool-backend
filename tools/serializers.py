from django.conf import settings
from rest_framework import serializers

MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


def _validate_pdf(f):
    if f.size > MAX_BYTES:
        raise serializers.ValidationError(
            f"File too large. Max {settings.MAX_UPLOAD_MB}MB."
        )
    if not f.name.lower().endswith(".pdf"):
        raise serializers.ValidationError("Only .pdf files are accepted.")
    return f


class MergeSerializer(serializers.Serializer):
    files = serializers.ListField(
        child=serializers.FileField(), min_length=2, allow_empty=False
    )

    def validate_files(self, value):
        return [_validate_pdf(f) for f in value]


class SingleFileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        return _validate_pdf(value)


class SplitSerializer(SingleFileSerializer):
    # e.g. "1-3,4-4,5-10"
    ranges = serializers.CharField()

    def validate_ranges(self, value):
        parsed = []
        for chunk in value.split(","):
            chunk = chunk.strip()
            if "-" in chunk:
                a, b = chunk.split("-", 1)
            else:
                a = b = chunk
            try:
                parsed.append((int(a), int(b)))
            except ValueError:
                raise serializers.ValidationError(f"Bad range: {chunk!r}")
        if not parsed:
            raise serializers.ValidationError("No valid ranges provided.")
        return parsed


class RotateSerializer(SingleFileSerializer):
    degrees = serializers.IntegerField(default=90)

    def validate_degrees(self, value):
        if value % 90 != 0:
            raise serializers.ValidationError("Degrees must be a multiple of 90.")
        return value
