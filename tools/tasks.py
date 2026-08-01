"""
Celery tasks for heavy jobs (conversion, OCR, large compression).
Wire these into views with .delay() once you add Redis + a worker.
For now the tools run synchronously in the request; move them here when
files get large or processing gets slow.
"""
from celery import shared_task

from . import services


@shared_task
def compress_pdf_task(data: bytes) -> bytes:
    return services.compress_pdf(data)
