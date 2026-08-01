FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System deps for pikepdf/pdf2image (add ghostscript, poppler, tesseract as you enable those tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqpdf-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media

# Non-root. Owns the dirs the entrypoint writes to (collectstatic, uploads).
RUN useradd --create-home --uid 10001 app \
    && chown -R app:app /app/staticfiles /app/media
USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
# 3 workers + 2 threads suits this box where the PDF work is CPU-bound but
# short. Long timeout because compressing a large PDF holds the worker.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
