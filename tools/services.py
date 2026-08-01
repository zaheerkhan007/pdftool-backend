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
