import io
import os
import zipfile

import pikepdf
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.http import FileResponse, JsonResponse
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from . import services
from .serializers import (
    ComparePdfSerializer,
    MergeSerializer,
    OfficeFileSerializer,
    PasswordSerializer,
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


def _discard_upload(f) -> None:
    """Immediately remove an uploaded file from disk (if it was spooled there)."""
    # Small uploads live in memory (nothing on disk); large ones are spooled to a
    # temp file by Django. Close + unlink so nothing lingers after processing.
    try:
        path = f.temporary_file_path() if isinstance(f, TemporaryUploadedFile) else None
    except Exception:
        path = None
    try:
        f.close()
    except Exception:
        pass
    if path:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


class ServerToolView(APIView):
    """
    Base for every file-processing endpoint. Guarantees uploaded files are NOT
    retained: once the response is built (the file is already in memory), we
    delete any on-disk temp upload and tag the response. Processing itself runs
    in memory or in auto-deleted temp dirs.
    """

    parser_classes = [MultiPartParser, FormParser]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        try:
            for key in request.FILES:
                for f in request.FILES.getlist(key):
                    _discard_upload(f)
        except Exception:
            pass
        response["X-File-Storage"] = "not-stored"
        return response


def health(_request):
    return JsonResponse({"status": "ok"})


class MergeView(ServerToolView):
    def post(self, request):
        s = MergeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        files = [f.read() for f in s.validated_data["files"]]
        return _pdf_response(services.merge_pdfs(files), "merged.pdf")


class SplitView(ServerToolView):
    def post(self, request):
        s = SplitSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        parts = services.split_pdf(data, s.validated_data["ranges"])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, part in enumerate(parts, start=1):
                zf.writestr(f"split_{i}.pdf", part)
        buf.seek(0)
        resp = FileResponse(buf, content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="split.zip"'
        return resp


class CompressView(ServerToolView):
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


class RotateView(ServerToolView):
    def post(self, request):
        s = RotateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        out = services.rotate_pdf(data, s.validated_data["degrees"])
        return _pdf_response(out, "rotated.pdf")


class PdfToJpgView(ServerToolView):
    def post(self, request):
        s = PdfToImagesSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        images = services.pdf_to_images(data, dpi=s.validated_data["dpi"], fmt="jpeg")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(images, start=1):
                zf.writestr(f"page_{i}.jpg", img)
        buf.seek(0)
        resp = FileResponse(buf, content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="images.zip"'
        resp["X-Page-Count"] = str(len(images))
        return resp


class PdfToWordView(ServerToolView):
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


class WordToPdfView(ServerToolView):
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


class ProtectView(ServerToolView):
    def post(self, request):
        s = PasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.protect_pdf(data, s.validated_data["password"])
        except Exception:
            return JsonResponse({"detail": "Could not protect this PDF."}, status=422)
        return _pdf_response(out, "protected.pdf")


class UnlockView(ServerToolView):
    def post(self, request):
        s = PasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.unlock_pdf(data, s.validated_data["password"])
        except pikepdf.PasswordError:
            return JsonResponse(
                {"detail": "Wrong password — could not unlock this PDF."}, status=400
            )
        except Exception:
            return JsonResponse({"detail": "Could not unlock this PDF."}, status=422)
        return _pdf_response(out, "unlocked.pdf")


class RepairView(ServerToolView):
    def post(self, request):
        s = SingleFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.repair_pdf(data)
        except Exception:
            return JsonResponse(
                {"detail": "Could not repair this PDF — it may be too damaged."},
                status=422,
            )
        return _pdf_response(out, "repaired.pdf")


class OfficeToPdfView(ServerToolView):
    """PowerPoint / Excel / HTML → PDF (all via LibreOffice, one endpoint each)."""

    def post(self, request):
        s = OfficeFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        upload = s.validated_data["file"]
        data = upload.read()
        try:
            out = services.office_to_pdf(data, upload.name)
        except RuntimeError as e:
            return JsonResponse({"detail": str(e)}, status=503)
        except Exception:
            return JsonResponse(
                {"detail": "Could not convert this file to PDF."}, status=422
            )
        return _pdf_response(out, "converted.pdf")


def _download(data: bytes, filename: str, content_type: str) -> FileResponse:
    resp = FileResponse(io.BytesIO(data), content_type=content_type)
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class PdfToMarkdownView(ServerToolView):
    def post(self, request):
        s = SingleFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.pdf_to_markdown(data)
        except Exception:
            return JsonResponse(
                {"detail": "Could not extract text from this PDF."}, status=422
            )
        return _download(out, "converted.md", "text/markdown; charset=utf-8")


class PdfToPptxView(ServerToolView):
    def post(self, request):
        s = SingleFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.pdf_to_pptx(data)
        except Exception:
            return JsonResponse(
                {"detail": "Could not convert this PDF to PowerPoint."}, status=422
            )
        return _download(out, "converted.pptx", _PPTX)


class PdfToXlsxView(ServerToolView):
    def post(self, request):
        s = SingleFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.pdf_to_xlsx(data)
        except Exception:
            return JsonResponse(
                {"detail": "Could not convert this PDF to Excel."}, status=422
            )
        return _download(out, "converted.xlsx", _XLSX)


class OcrView(ServerToolView):
    def post(self, request):
        s = SingleFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.ocr_pdf(data)
        except RuntimeError as e:
            return JsonResponse({"detail": str(e)}, status=503)
        except Exception:
            return JsonResponse({"detail": "Could not OCR this PDF."}, status=422)
        return _pdf_response(out, "ocr.pdf")


class PdfToPdfaView(ServerToolView):
    def post(self, request):
        s = SingleFileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data["file"].read()
        try:
            out = services.pdf_to_pdfa(data)
        except RuntimeError as e:
            return JsonResponse({"detail": str(e)}, status=503)
        except Exception:
            return JsonResponse(
                {"detail": "Could not convert this PDF to PDF/A."}, status=422
            )
        return _pdf_response(out, "converted-pdfa.pdf")


class ComparePdfView(ServerToolView):
    def post(self, request):
        s = ComparePdfSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        a = s.validated_data["file"].read()
        b = s.validated_data["other"].read()
        try:
            out = services.compare_pdfs(a, b)
        except Exception:
            return JsonResponse(
                {"detail": "Could not compare these PDFs."}, status=422
            )
        return _pdf_response(out, "comparison.pdf")
