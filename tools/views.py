import io
import zipfile

from django.http import FileResponse, JsonResponse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from . import services
from .serializers import (
    MergeSerializer,
    RotateSerializer,
    SingleFileSerializer,
    SplitSerializer,
)


def _pdf_response(data: bytes, filename: str) -> FileResponse:
    resp = FileResponse(io.BytesIO(data), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def health(_request):
    return JsonResponse({"status": "ok"})


class MergeView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = MergeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        files = [f.read() for f in s.validated_data["files"]]
        return _pdf_response(services.merge_pdfs(files), "merged.pdf")


class SplitView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = SplitSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        parts = services.split_pdf(data, s.validated_data["ranges"])
        # Return a zip of the parts
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, part in enumerate(parts, start=1):
                zf.writestr(f"split_{i}.pdf", part)
        buf.seek(0)
        resp = FileResponse(buf, content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="split.zip"'
        return resp


class CompressView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = SingleFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        original = len(data)
        out = services.compress_pdf(data)
        resp = _pdf_response(out, "compressed.pdf")
        resp["X-Original-Size"] = str(original)
        resp["X-Compressed-Size"] = str(len(out))
        return resp


class RotateView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = RotateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        out = services.rotate_pdf(data, s.validated_data["degrees"])
        return _pdf_response(out, "rotated.pdf")
