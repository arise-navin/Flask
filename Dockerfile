# Use a lightweight Python image
FROM python:3.10-slim

# --- metadata / build args ---
ARG SAMPLE_FILE_PATH="/mnt/data/WhatsApp Image 2025-11-14 at 16.18.40_db80ed74.jpg"

# Make the sample file path available as an env var inside the container.
ENV SAMPLE_FILE_URL=${SAMPLE_FILE_PATH}
ENV OCR_API_KEY=""
ENV GEMINI_API_KEY=""
# ENV GEMINI_MODEL="gemini-1.5-pro-latest"

# Install system dependencies required for OCR / PDF -> image conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    wget \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirement file and install python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
COPY . /app

# Expose both ports (Flask + FastAPI)
EXPOSE 5000 8000

# Default command - starts the combined server (threaded)
CMD ["python", "main.py"]
