FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
# System deps:
#  - libqpdf-dev, gcc      : pikepdf build
#  - libreoffice-writer    : Word → PDF conversion (the only tool needing a binary)
#  - libglib2.0-0          : runtime lib for opencv-headless (pulled in by pdf2docx)
#  - fonts-dejavu-core     : sane default fonts so converted PDFs aren't blank/boxes
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqpdf-dev gcc \
    libreoffice-writer \
    libglib2.0-0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
