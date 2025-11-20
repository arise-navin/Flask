# ------------------------------
# Base Image
# ------------------------------
FROM python:3.11-slim

# ------------------------------
# System dependencies for OCR
# ------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libsm6 \
    libxext6 \
    libxrender1 \
    libglib2.0-0 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------
# Working directory
# ------------------------------
WORKDIR /app

# ------------------------------
# Install Python dependencies
# ------------------------------
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ------------------------------
# Copy application files
# ------------------------------
COPY . /app

# ------------------------------
# Expose Flask port
# ------------------------------
EXPOSE 5000

# ------------------------------
# Start Flask app
# ------------------------------
CMD ["python", "main.py"]
