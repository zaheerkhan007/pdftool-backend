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


def _validate_docx(f):
    if f.size > MAX_BYTES:
        raise serializers.ValidationError(
            f"File too large. Max {settings.MAX_UPLOAD_MB}MB."
        )
    if not f.name.lower().endswith((".docx", ".doc")):
        raise serializers.ValidationError("Only .docx / .doc files are accepted.")
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


class WordFileSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        return _validate_docx(value)


class PdfToImagesSerializer(SingleFileSerializer):
    dpi = serializers.IntegerField(default=150)

    def validate_dpi(self, value):
        # Keep it sane so a huge PDF can't blow up memory.
        return max(72, min(300, value))


class PasswordSerializer(SingleFileSerializer):
    password = serializers.CharField(min_length=1, max_length=256, trim_whitespace=False)


OFFICE_EXTS = (
    ".ppt", ".pptx", ".xls", ".xlsx", ".html", ".htm",
    ".doc", ".docx", ".odt", ".ods", ".odp", ".csv", ".rtf", ".txt",
)


class OfficeFileSerializer(serializers.Serializer):
    """Any office / HTML document LibreOffice can turn into a PDF."""
    file = serializers.FileField()

    def validate_file(self, value):
        if value.size > MAX_BYTES:
            raise serializers.ValidationError(
                f"File too large. Max {settings.MAX_UPLOAD_MB}MB."
            )
        if not value.name.lower().endswith(OFFICE_EXTS):
            raise serializers.ValidationError("Unsupported file type.")
        return value


class TranslateSerializer(SingleFileSerializer):
    target_language = serializers.CharField(max_length=60)


class TrackSerializer(serializers.Serializer):
    """
    A browser-side tool reporting that it produced a result.

    Deliberately minimal: a slug, a count and a byte total. There is no field
    here for a filename or anything derived from the document, so this endpoint
    cannot be used to record what someone processed even by accident.
    """

    # Matches the slug format used by /tools/<slug>; the regex is the whole
    # validation, since the backend has no copy of the frontend's catalog.
    tool = serializers.RegexField(r"^[a-z0-9][a-z0-9-]{0,49}$")
    files = serializers.IntegerField(min_value=1, max_value=1000, default=1)
    # Capped rather than unbounded so a bad or malicious client cannot skew the
    # dashboard's byte totals into meaninglessness. 2GB is far above any real
    # browser-side output.
    bytes = serializers.IntegerField(min_value=0, max_value=2_147_483_648, default=0)


class ComparePdfSerializer(serializers.Serializer):
    file = serializers.FileField()
    other = serializers.FileField()

    def validate_file(self, value):
        return _validate_pdf(value)

    def validate_other(self, value):
        return _validate_pdf(value)
