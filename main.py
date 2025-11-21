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

app = Flask(__name__)

OCR_API_KEY = os.getenv("OCR_API_KEY", "")
LANGUAGE = "eng"

PII_LABELS = [

    # -----------------------------
    # 1. Government Issued ID
    # -----------------------------
    "government issued id", "Government Issued ID", "GOVERNMENT ISSUED ID",
    "govt issued id", "gov issued id", "gov issued identification",
    "gov id", "govt id", "government id", "government identification",
    "id issued by government", "government identity card",
    "id card", "identity card", "identification id",
    "official id", "official identification", "national id",
    "national identification", "gov identity",

    # -----------------------------
    # 2. Social Security Number
    # -----------------------------
    "social security number", "Social Security Number", "SOCIAL SECURITY NUMBER",
    "ssn", "SSN", "S.S.N.", "social security no", "ss number",
    "soc sec no", "ssn number", "social sec number", "social security #",

    # -----------------------------
    # 3. Tax ID
    # -----------------------------
    "tax id", "Tax ID", "TAX ID", "tax identification number",
    "tin", "TIN", "T.I.N.", "tax no", "tax number",
    "taxpayer id", "tax payer number",

    # -----------------------------
    # 4. Federal Employer ID
    # -----------------------------
    "federal employer id", "Federal Employer ID", "FEDERAL EMPLOYER ID",
    "employer id", "employer identification", "feid", "FEID", "F.E.I.D.",

    # -----------------------------
    # 5. FEIN
    # -----------------------------
    "fein", "FEIN", "F.E.I.N.", "federal employer identification number",
    "fein number", "federal ein", "employer ein",

    # -----------------------------
    # 6. Driver's License
    # -----------------------------
    "driver's license", "Driver's License", "Driver' s License","License","DRIVER'S LICENSE",
    "drivers license", "driver license", "driving license",
    "dl number", "DL", "D.L.", "license number", "driver id",

    # -----------------------------
    # 7. Identification Card
    # -----------------------------
    "identification card", "Identification Card", "ID card",
    "identity card", "id", "ID", "identification", "id number",
    "identification number",

    # -----------------------------
    # 8. Passport
    # -----------------------------
    "passport", "Passport", "PASSPORT", "passport number",
    "passport no", "pp number", "passport id",

    # -----------------------------
    # 9. Military ID
    # -----------------------------
    "military id", "Military ID", "MILITARY ID",
    "army id", "navy id", "airforce id", "defense id",
    "military identification",

    # -----------------------------
    # 10. Date of Birth
    # -----------------------------
    "date of birth", "Date of Birth", "DATE OF BIRTH",
    "dob", "DOB", "birth date", "birth info","D.o.B.","DOB",
    "date born", "born on", "birthdate","D.O.B.",

    # -----------------------------
    # 11. Home Address
    # -----------------------------
    "home address", "Home Address", "HOME ADDRESS",
    "residential address", "residence address", "address", "addr","ADDRESS",
    "street address", "street addr", "residential addr","Address",

    # -----------------------------
    # 12. Home Telephone Number
    # -----------------------------
    "home telephone number", "Home Telephone number",
    "HOME TELEPHONE NUMBER", "telephone number",
    "home phone", "landline", "tel number",

    # -----------------------------
    # 13. Cell Phone Number
    # -----------------------------
    "cell phone number", "Cell phone number", "CELL PHONE NUMBER",
    "mobile number", "mobile no", "cell number", "phone number",
    "contact number", "contact no","ph number","Cell No",

    # -----------------------------
    # 14. Email Address
    # -----------------------------
    "email address", "Email Address", "EMAIL ADDRESS",
    "email", "e-mail", "email id", "mail id","Email","email ID","eMail","gmail","g-mail",

    # -----------------------------
    # 15. Social Media Contact Information
    # -----------------------------
    "social media contact information", "Social Media Contact Information",
    "SOCIAL MEDIA CONTACT INFORMATION", "social media info",
    "social handle", "social contact", "social media account",

    # -----------------------------
    # 16. Health Insurance Policy Number
    # -----------------------------
    "health insurance policy number", "Health Insurance Policy Number",
    "insurance policy number", "policy number", "policy no",
    "health insurance number", "insurance number",

    # -----------------------------
    # 17. Medical Record Number
    # -----------------------------
    "medical record number", "Medical Record Number",
    "MRN", "mrn", "medical record no", "med record number","medical","record","number",

    # -----------------------------
    # 18. Claim Number
    # -----------------------------
    "claim number", "Claim Number", "CLAIM NUMBER",
    "claim no", "claim id",

    # -----------------------------
    # 19. Patient Account Number
    # -----------------------------
    "patient account number", "Patient Account Number",
    "PATIENT ACCOUNT NUMBER", "patient id", "patient account",

    # -----------------------------
    # 20. File Number
    # -----------------------------
    "file number", "File Number", "FILE NUMBER",
    "file no", "file id", "file reference",

    # -----------------------------
    # 21. Chart Number
    # -----------------------------
    "chart number", "Chart Number", "CHART NUMBER",
    "chart no", "chart id",

    # -----------------------------
    # 22. Individual Financial Account Number
    # -----------------------------
    "individual financial account number", "Individual Financial Account Number",
    "financial account number", "financial account", "account number",

    # -----------------------------
    # 23. Bank Account Number
    # -----------------------------
    "bank account number", "Bank Account Number", "BANK ACCOUNT NUMBER",
    "bank no", "account no", "acct number",

    # -----------------------------
    # 24. Financial Information
    # -----------------------------
    "financial information", "Financial Information",
    "FINANCIAL INFORMATION", "financial data", "financial details",

    # -----------------------------
    # 25. Credit Card Number
    # -----------------------------
    "credit card number", "Credit Card Number", "CREDIT CARD NUMBER",
    "credit card", "card number", "cc number", "card no"
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


def blackout(match):
    return "█" * len(match.group(0))


def detect_filetype(filename):
    ext = filename.lower().split(".")[-1]
    if ext in ("jpg", "jpeg", "png"):
        return "image"
    if ext == "pdf":
        return "pdf"
    if ext == "txt":
        return "text"
    if ext == "docx":
        return "docx"
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

    # Try OCR.space API
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

    # Fallback pytesseract
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

    # Regex PII
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
