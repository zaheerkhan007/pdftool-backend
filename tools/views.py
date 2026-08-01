import io
import zipfile

from django.http import FileResponse, JsonResponse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from . import services
from .serializers import (
    MergeSerializer,
    PdfToImagesSerializer,
    RotateSerializer,
    SingleFileSerializer,
    SplitSerializer,
    WordFileSerializer,
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


class PdfToJpgView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = PdfToImagesSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        images = services.pdf_to_images(data, dpi=s.validated_data["dpi"], fmt="jpeg")
        # Zip the pages so the browser gets a single download.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(images, start=1):
                zf.writestr(f"page_{i}.jpg", img)
        buf.seek(0)
        resp = FileResponse(buf, content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="images.zip"'
        resp["X-Page-Count"] = str(len(images))
        return resp


class PdfToWordView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = SingleFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.pdf_to_docx(data)
        except RuntimeError as e:
            return JsonResponse({"detail": str(e)}, status=503)
        except Exception:
            return JsonResponse(
                {"detail": "Could not convert this PDF to Word."}, status=422
            )
        resp = FileResponse(
            io.BytesIO(out),
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
        )
        resp["Content-Disposition"] = 'attachment; filename="converted.docx"'
        return resp


class WordToPdfView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        s = WordFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        upload = s.validated_data["file"]
        data = upload.read()
        try:
            out = services.docx_to_pdf(data, upload.name)
        except RuntimeError as e:
            # LibreOffice missing → clear, non-fatal 503 (other tools unaffected).
            return JsonResponse({"detail": str(e)}, status=503)
        except Exception:
            return JsonResponse(
                {"detail": "Could not convert this document to PDF."}, status=422
            )
        return _pdf_response(out, "converted.pdf")
