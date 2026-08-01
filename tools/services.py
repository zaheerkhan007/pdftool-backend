"""
Real PDF processing logic. Each function takes file bytes / paths and returns
processed bytes. Keep these framework-agnostic so they can run inside a Celery
worker or directly in a request.
"""
import io
from typing import List

import pikepdf
from pypdf import PdfReader, PdfWriter


def merge_pdfs(files: List[bytes]) -> bytes:
    """Merge multiple PDFs (in order) into one."""
    writer = PdfWriter()
    for data in files:
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def split_pdf(data: bytes, ranges: List[tuple]) -> List[bytes]:
    """
    Split a PDF into multiple files by page ranges.
    ranges: list of (start, end) 1-indexed inclusive tuples.
    Returns one PDF (bytes) per range.
    """
    reader = PdfReader(io.BytesIO(data))
    total = len(reader.pages)
    results = []
    for start, end in ranges:
        start = max(1, start)
        end = min(total, end)
        writer = PdfWriter()
        for i in range(start - 1, end):
            writer.add_page(reader.pages[i])
        buf = io.BytesIO()
        writer.write(buf)
        results.append(buf.getvalue())
    return results


def compress_pdf(data: bytes) -> bytes:
    """
    Lossless-ish compression via pikepdf: object-stream compression, removes
    unused objects, and re-encodes. For aggressive image downsampling you'd
    add Ghostscript (see README) — this is the safe, dependency-light path.
    """
    with pikepdf.open(io.BytesIO(data)) as pdf:
        out = io.BytesIO()
        pdf.save(
            out,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            recompress_flate=True,
        )
        return out.getvalue()


def rotate_pdf(data: bytes, degrees: int = 90) -> bytes:
    """Rotate every page by `degrees` (must be a multiple of 90)."""
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for page in reader.pages:
        page.rotate(degrees)
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def pdf_page_count(data: bytes) -> int:
    return len(PdfReader(io.BytesIO(data)).pages)


def protect_pdf(data: bytes, password: str) -> bytes:
    """Encrypt a PDF with a password (AES-256)."""
    with pikepdf.open(io.BytesIO(data)) as pdf:
        out = io.BytesIO()
        pdf.save(
            out,
            encryption=pikepdf.Encryption(owner=password, user=password, R=6),
        )
        return out.getvalue()


def unlock_pdf(data: bytes, password: str) -> bytes:
    """
    Remove a known password from a PDF. Raises pikepdf.PasswordError if the
    password is wrong (the view turns that into a clean 400).
    """
    with pikepdf.open(io.BytesIO(data), password=password) as pdf:
        out = io.BytesIO()
        pdf.save(out)  # saving without an encryption arg drops the encryption
        return out.getvalue()


def pdf_to_images(data: bytes, dpi: int = 150, fmt: str = "jpeg") -> List[bytes]:
    """
    Render each PDF page to a raster image using PyMuPDF (fitz).
    We use PyMuPDF instead of pdf2image/poppler on purpose: it ships as a
    self-contained wheel, so there are NO system packages to install (works
    the same on Windows dev and in the slim Docker image).
    Returns one image (bytes) per page.
    """
    import fitz  # PyMuPDF — imported lazily so the other tools work without it

    images: List[bytes] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            images.append(pix.tobytes(fmt))
    return images


def pdf_to_docx(data: bytes) -> bytes:
    """
    Convert a PDF into an editable Word (.docx) using pdf2docx (pure pip, no
    system binaries). It reconstructs text, tables and basic layout.
    """
    import os
    import tempfile

    from pdf2docx import Converter  # lazy import — keeps other tools dep-free

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "in.pdf")
        docx_path = os.path.join(tmp, "out.docx")
        with open(pdf_path, "wb") as fh:
            fh.write(data)
        cv = Converter(pdf_path)
        try:
            cv.convert(docx_path)  # all pages
        finally:
            cv.close()
        with open(docx_path, "rb") as fh:
            return fh.read()


def docx_to_pdf(data: bytes, filename: str = "document.docx") -> bytes:
    """
    Convert a Word document to PDF via LibreOffice headless (`soffice`).
    This is the one tool that needs a system binary. If LibreOffice isn't
    installed we raise a clear error (the view turns it into a 503) instead of
    crashing — so this tool degrades gracefully and never affects the others.
    """
    import glob
    import os
    import shutil
    import subprocess
    import tempfile

    # Find LibreOffice. On PATH (Docker/Linux) or common Windows install dirs,
    # since the Windows installer doesn't add `soffice` to PATH.
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        for candidate in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            if os.path.exists(candidate):
                soffice = candidate
                break
    if not soffice:
        raise RuntimeError(
            "Word→PDF needs LibreOffice on the server. Install the "
            "'libreoffice-writer' package (already added to the Dockerfile) and "
            "redeploy, or install LibreOffice locally to test on Windows."
        )

    with tempfile.TemporaryDirectory() as tmp:
        ext = os.path.splitext(filename)[1].lower() or ".docx"
        in_path = os.path.join(tmp, "input" + ext)
        with open(in_path, "wb") as fh:
            fh.write(data)
        # A private user-profile dir avoids clashes when requests run in parallel.
        profile = "-env:UserInstallation=file://" + os.path.join(tmp, "lo_profile")
        subprocess.run(
            [soffice, profile, "--headless", "--convert-to", "pdf",
             "--outdir", tmp, in_path],
            check=True, timeout=120,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        pdfs = glob.glob(os.path.join(tmp, "*.pdf"))
        if not pdfs:
            raise RuntimeError("LibreOffice produced no PDF output.")
        with open(pdfs[0], "rb") as fh:
            return fh.read()
