import os
import re
import pytesseract
import pdfplumber
from PIL import Image
from pdf2image import convert_from_path
from collections import Counter
from docx import Document

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Poppler path for scanned PDFs
POPPLER_PATH = r"C:\poppler\Release-25.12.0-0\Library\bin"

STOPWORDS = {
    "the", "is", "in", "and", "to", "of", "a", "for", "on", "with", "that",
    "this", "it", "as", "are", "an", "be", "by", "or", "from", "at", "was",
    "were", "has", "have", "had", "will", "can", "not", "but", "their", "they",
    "them", "its", "if", "into", "than", "then", "also", "about", "such", "using",
    "use", "used", "may", "more", "other", "these", "those", "which", "who", "when",
    "where", "how", "what", "why", "your", "our", "we", "you"
}

SUSPICIOUS_KEYWORDS = [
    "edited", "fake", "tampered", "modified", "overwrite",
    "overwritten", "duplicate", "mismatch", "inconsistent"
]


def clean_text(text):
    if not text:
        return ""
    text = text.replace("\x0c", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text):
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def generate_document_summary(text, max_sentences=3):
    text = clean_text(text)

    if not text:
        return "No readable content found."

    sentences = split_sentences(text)

    # Filter meaningful sentences
    sentences = [s for s in sentences if len(s.split()) > 5]

    if not sentences:
        return "The document contains limited meaningful content."

    # Prefer sentences with important keywords
    important_keywords = [
        "project", "system", "analysis", "objective",
        "technology", "platform", "data", "model",
        "invoice", "payment", "certificate", "result"
    ]

    scored = []

    for s in sentences:
        score = 0
        lower = s.lower()

        for word in important_keywords:
            if word in lower:
                score += 2

        score += len(s.split()) / 10

        scored.append((s, score))

    top = sorted(scored, key=lambda x: x[1], reverse=True)[:max_sentences]

    summary = " ".join([s for s, _ in top])

    if len(summary) > 300:
        summary = summary[:300] + "..."

    return summary


def detect_document_type(text, filename=""):
    lower_text = text.lower()
    lower_name = filename.lower()

    if any(word in lower_text for word in ["invoice", "gst", "bill no", "amount due", "tax invoice"]):
        return "Invoice"
    elif any(word in lower_text for word in ["receipt", "transaction", "upi", "paid", "debited", "credited"]):
        return "Payment Receipt"
    elif any(word in lower_text for word in ["certificate", "certified", "completion", "awarded"]):
        return "Certificate"
    elif any(word in lower_text for word in ["resume", "curriculum vitae", "education", "skills", "experience"]):
        return "Resume"
    elif any(word in lower_text for word in ["aadhaar", "identity", "id number", "date of birth"]):
        return "Identity Document"
    elif any(word in lower_text for word in ["mark", "grade", "student", "college", "university"]):
        return "Academic Document"
    elif any(word in lower_name for word in ["invoice", "receipt", "certificate", "resume", "payment", "aadhaar", "id"]):
        return "Document Image"
    else:
        return "General Document"


def find_suspicious_keywords(text):
    found = []
    lower_text = text.lower()
    for word in SUSPICIOUS_KEYWORDS:
        if word in lower_text:
            found.append(word)
    return found


def get_text_quality(text):
    if not text:
        return {"length": 0, "alpha_ratio": 0, "readable": False}

    total_chars = len(text)
    alpha_count = sum(c.isalpha() for c in text)
    alpha_ratio = alpha_count / total_chars if total_chars else 0
    readable = total_chars > 40 and alpha_ratio > 0.30

    return {
        "length": total_chars,
        "alpha_ratio": alpha_ratio,
        "readable": readable
    }


def extract_text_from_image(file_path):
    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        text = clean_text(text)
        return text if text else "No readable text found in image."
    except Exception:
        return "No readable text found in image."


def extract_text_from_pdf(file_path):
    # 1. normal PDF text extraction
    try:
        all_text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:5]:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)

        joined = clean_text("\n\n".join(all_text))
        if joined:
            return joined
    except Exception:
        pass

    # 2. OCR fallback for scanned PDFs
    try:
        pages = convert_from_path(
            file_path,
            first_page=1,
            last_page=3,
            poppler_path=POPPLER_PATH
        )

        ocr_text = []
        for page_image in pages:
            text = pytesseract.image_to_string(page_image)
            text = clean_text(text)
            if text:
                ocr_text.append(text)

        joined = clean_text("\n\n".join(ocr_text))
        return joined if joined else "No readable text found in PDF."
    except Exception:
        return "No readable text found in PDF."


def build_result(text, filename):
    text = clean_text(text)
    doc_type = detect_document_type(text, filename)
    quality = get_text_quality(text)
    suspicious_words = find_suspicious_keywords(text)
    summary = generate_document_summary(text)

    reasons = []
    lower_text = text.lower()

    # 1. Readability / extraction quality checks
    if not text or "no readable text found" in lower_text:
        reasons.append("Very little readable content was extracted from the document.")

    if quality["length"] < 50:
        reasons.append("The document contains too little extracted text for strong verification.")

    if not quality["readable"]:
        reasons.append("The extracted text quality is weak or incomplete.")

    # 2. Suspicious keyword checks
    if suspicious_words:
        reasons.append(f"Suspicious keywords were detected: {', '.join(suspicious_words)}.")

    # 3. Repeated symbol / noisy OCR checks
    noisy_patterns = ["@@@", "###", "$$$", "~~~", "|||"]
    found_noise = [p for p in noisy_patterns if p in text]
    if found_noise:
        reasons.append("Unusual character patterns were found in the extracted text.")

    # 4. Document-specific checks
    if doc_type == "Invoice":
        if "invoice" not in lower_text:
            reasons.append("The document does not clearly contain an invoice heading.")
        if "amount" not in lower_text and "total" not in lower_text:
            reasons.append("Expected invoice-related fields like amount or total are missing.")
        if "date" not in lower_text:
            reasons.append("Expected invoice field 'Date' appears to be missing.")

    elif doc_type == "Payment Receipt":
        if "payment" not in lower_text and "transaction" not in lower_text and "receipt" not in lower_text:
            reasons.append("The document does not clearly contain payment-related wording.")
        if "amount" not in lower_text and "paid" not in lower_text:
            reasons.append("Expected payment-related fields are missing.")
        if "date" not in lower_text and "time" not in lower_text:
            reasons.append("Expected transaction date or time details appear incomplete.")

    elif doc_type == "Certificate":
        if "certificate" not in lower_text and "certified" not in lower_text:
            reasons.append("The document does not clearly contain certificate-related wording.")
        if "awarded" not in lower_text and "completion" not in lower_text and "presented to" not in lower_text:
            reasons.append("Expected certificate-related details appear incomplete.")
        if "date" not in lower_text:
            reasons.append("Expected certificate issue date appears to be missing.")

    elif doc_type == "Resume":
        if "education" not in lower_text:
            reasons.append("Expected resume section 'Education' is missing.")
        if "skills" not in lower_text:
            reasons.append("Expected resume section 'Skills' is missing.")
        if "experience" not in lower_text:
            reasons.append("Expected resume section 'Experience' is missing.")

    elif doc_type == "Identity Document":
        if "id" not in lower_text and "identity" not in lower_text and "aadhaar" not in lower_text:
            reasons.append("The document does not clearly contain identity-related wording.")
        if "date of birth" not in lower_text and "dob" not in lower_text:
            reasons.append("Expected identity field 'Date of Birth' is missing.")
        if "name" not in lower_text:
            reasons.append("Expected identity field 'Name' appears to be missing.")

    # 5. Verdict logic
    strong_signs = 0

    for r in reasons:
        if any(word in r.lower() for word in [
            "suspicious keywords",
            "unusual character patterns",
            "weak or incomplete",
            "missing",
            "too little extracted text"
        ]):
            strong_signs += 1

    if len(reasons) == 0:
        verdict = "Likely Genuine"
        confidence = "90%"
        reasons = ["No major suspicious issues were detected."]
    elif strong_signs == 1:
        verdict = "Suspicious"
        confidence = "72%"
    elif strong_signs == 2:
        verdict = "Suspicious"
        confidence = "79%"
    else:
        verdict = "Likely Tampered"
        confidence = "86%"

    return {
        "doc_type": doc_type,
        "source_text": summary,
        "verdict": verdict,
        "confidence": confidence,
        "reasons": reasons
    }

def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        text = []

        for para in doc.paragraphs:
            if para.text.strip():
                text.append(para.text)

        return "\n".join(text) if text else "No readable text found in document."
    except Exception:
        return "Could not read DOCX file."

def analyze_file(file_path, filename):
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            text = ""
        return build_result(text, filename)

    elif ext in [".jpg", ".jpeg", ".png"]:
        text = extract_text_from_image(file_path)
        return build_result(text, filename)

    elif ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        return build_result(text, filename)
    
    elif ext == ".docx":
        text = extract_text_from_docx(file_path)
        return build_result(text, filename)

    else:
        return {
            "source_text": "Unsupported file type.",
            "verdict": "Needs Review",
            "confidence": "50%",
            "reasons": ["This file type is not supported for analysis."]
        }