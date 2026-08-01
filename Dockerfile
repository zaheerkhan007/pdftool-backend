FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
# System deps for pikepdf/pdf2image (add ghostscript, poppler, tesseract as you enable those tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libqpdf-dev gcc \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
