import os
import re
import io
import base64
import tempfile
import traceback
from io import BytesIO

from flask import Flask, request, send_file
import requests

# OCR libs
try:
    from pdf2image import convert_from_path
except:
    convert_from_path = None

try:
    from PIL import Image
except:
    Image = None

try:
    import pytesseract
except:
    pytesseract = None

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
app = Flask(__name__)

OCR_API_KEY = os.getenv("OCR_API_KEY", "")
LANGUAGE = "eng"

# ---------------------------------------------------
# PII LABELS & REGEX
# ---------------------------------------------------
PII_LABELS = [
    "government issued id", "Government Issued ID",
    "social security number", "Social Security Number",
    "tax id", "Tax ID",
    "federal employer id", "Federal Employer ID",
    "fein", "FEIN",
    "driver's license", "Driver's License",
    "identification card", "Identification Card",
    "passport", "Passport",
    "military id", "Military ID",
    "date of birth", "Date of Birth", "DOB",
    "home address", "Home Address",
    "home telephone number", "Home Telephone Number",
    "cell phone number", "Cell Phone Number",
    "email address", "Email Address",
    "social media contact information",
    "health insurance policy number",
    "medical record number",
    "claim number",
    "patient account number",
    "file number",
    "chart number",
    "bank account number",
    "financial information",
    "credit card number"
]

PII_REGEX = {
    "EMAIL": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "PHONE": r"\+?\d[\d\s\-\(\)]{7,}\d",
    "AADHAAR": r"\b\d{4}\s\d{4}\s\d{4}\b",
    "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "PASSPORT": r"\b[A-Z]{1}-?\d{7}\b",
    "CREDIT_CARD": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "DOB": r"\b(?:0?[1-9]|[12]\d|3[01])[\/\-\.](?:0?[1-9]|1[012])[\/\-\.](?:19|20)\d\d\b"
}


# ---------------------------------------------------
# Helper functions
# ---------------------------------------------------
def blackout(match):
    return "█" * len(match.group(0))


def detect_filetype(filename):
    ext = filename.lower().split(".")[-1]
    if ext in ("jpg", "jpeg", "png"): return "image"
    if ext == "pdf": return "pdf"
    if ext == "txt": return "text"
    if ext == "docx": return "docx"
    return "unknown"


def extract_text(file_bytes, filename, language="eng"):
    ftype = detect_filetype(filename)

    if ftype == "text":
        return file_bytes.decode("utf-8", errors="ignore")

    if ftype == "docx":
        from docx import Document
        with tempfile.NamedTemporaryFile(suffix=".docx") as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            doc = Document(tmp.name)
            return "\n".join(p.text for p in doc.paragraphs)

    # OCR: OCR.Space first
    if OCR_API_KEY:
        try:
            resp = requests.post(
                "https://api.ocr.space/parse/image",
                files={"file": (filename, file_bytes)},
                data={"apikey": OCR_API_KEY, "language": language}
            ).json()

            if not resp.get("IsErroredOnProcessing"):
                return "\n".join(r.get("ParsedText", "") for r in resp.get("ParsedResults", []))
        except:
            pass

    # fallback pytesseract
    if pytesseract and Image:
        try:
            img = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(img)
        except:
            pass

    return ""


def redact_text(text):
    # Label-based
    for label in PII_LABELS:
        pattern = rf"({label}\s*[:\-–]\s*)([^\n\r]+)"
        text = re.sub(pattern, lambda m: m.group(1) + blackout(m), text, flags=re.I)

    # Regex
    for patt in PII_REGEX.values():
        text = re.sub(patt, blackout, text)

    # Long numbers
    text = re.sub(r"\b\d{6,}\b", blackout, text)

    return text


def create_pdf(text):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf)
    style = getSampleStyleSheet()["Normal"]
    story = [Paragraph(line, style) for line in text.splitlines()]
    doc.build(story)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------
# FLASK ROUTE — Only One API
# ---------------------------------------------------
@app.route("/process_raw_pdf", methods=["POST"])
def process_raw_pdf():
    try:
        file_bytes = request.get_data()
        filename = request.headers.get("X-Filename", "document.pdf")

        extracted = extract_text(file_bytes, filename)
        if not extracted.strip():
            return {"error": "Could not extract text"}, 422

        redacted = redact_text(extracted)
        pdf = create_pdf(redacted)

        return send_file(
            BytesIO(pdf),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="processed.pdf"
        )

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}, 500


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
