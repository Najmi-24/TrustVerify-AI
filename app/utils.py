import os
import re
import pytesseract
import pdfplumber
import google.generativeai as genai
from pdf2image import convert_from_path
from collections import Counter
from docx import Document
from PIL import Image, ImageChops, ImageEnhance


# Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR"

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
    "overwritten", "duplicate", "mismatch", "inconsistent",
    "invalid", "not valid", "sample", "dummy", "test document",
    "forged", "copy", "unauthorized", "manipulated"
]
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")
else:
    gemini_model = None


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
        image = Image.open(file_path).convert("L")  # makes image clearer

        text = pytesseract.image_to_string(image)

        print("EXTRACTED IMAGE TEXT:", text)

        text = clean_text(text)

        if not text or len(text) < 10:
            return "No readable text found in image."

        return text

    except Exception as e:
        print("IMAGE ERROR:", e)
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
    
    def gemini_summary_and_advice(text, doc_type):
    if not gemini_model or not text or len(text) < 30:
        return None

    try:
        prompt = f"""
Analyze this {doc_type}.

Return only:
Summary: one short paragraph
Suspicious Points: 2-4 bullet points
Advice: one practical sentence

Document:
{text[:3000]}
"""
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("GEMINI ERROR:", e)
        return None
    
def build_result(text, filename):
    text = clean_text(text)
    doc_type = detect_document_type(text, filename)
    quality = get_text_quality(text)
    suspicious_words = find_suspicious_keywords(text)

    raw_summary = generate_document_summary(text)
    gemini_output = gemini_summary_and_advice(text, doc_type)
    if gemini_output:
     raw_summary = gemini_output

    # Short summary
    summary = raw_summary
    if len(summary.split()) > 40:
        summary = " ".join(summary.split()[:40]) + "..."

    reasons = []
    lower_text = text.lower()

    # Basic checks
    if not text or "no readable text found" in lower_text:
        reasons.append("Very little readable content was extracted from the document.")

    if quality["length"] < 50:
        reasons.append("The document contains too little extracted text.")

    if not quality["readable"]:
        reasons.append("The extracted text quality is weak or incomplete.")

    if suspicious_words:
        reasons.append(f"Suspicious keywords detected: {', '.join(suspicious_words)}.")

    # Clean reasons
    reasons = list(dict.fromkeys(reasons))
    if len(reasons) > 4:
        reasons = reasons[:4]

    # Verdict logic
    strong_signs = len(reasons)

    if strong_signs == 0:
        verdict = "Likely Genuine"
        confidence = "90%"
        reasons = ["No major suspicious issues detected."]
    elif strong_signs <= 2:
        verdict = "Suspicious"
        confidence = "72%"
    else:
        verdict = "Likely Tampered"
        confidence = "86%"

    # Advice
    if "Tampered" in verdict or "Suspicious" in verdict:
        advice = "This document may be unreliable. Verify key fields with official sources."
    else:
        advice = "No major issues detected, but always verify important documents."

    return {
        "doc_type": doc_type,
        "source_text": summary,
        "full_text": text,
        "summary": summary,
        "verdict": verdict,
        "confidence": confidence,
        "reasons": reasons,
        "advice": advice
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

    if ext in [".jpg", ".jpeg", ".png"]:
        text = extract_text_from_image(file_path)
        result = build_result(text, filename)

        ela_result = perform_ela_analysis(file_path)

        result["ela_score"] = ela_result["ela_score"]

        if ela_result["ela_flag"]:
            result["reasons"].append(ela_result["ela_reason"])

            if result["verdict"] == "Likely Genuine":
                result["verdict"] = "Suspicious"
                result["confidence"] = "72%"

        return result

    elif ext == ".pdf":
        text = extract_text_from_pdf(file_path)
        return build_result(text, filename)

    elif ext == ".docx":
        text = extract_text_from_docx(file_path)
        return build_result(text, filename)

    else:
        return build_result("", filename)
def perform_ela_analysis(image_path):
    try:
        original = Image.open(image_path).convert("RGB")

        temp_path = image_path + "_ela_temp.jpg"
        original.save(temp_path, "JPEG", quality=90)

        compressed = Image.open(temp_path)
        ela_image = ImageChops.difference(original, compressed)

        extrema = ela_image.getextrema()
        max_diff = max([ex[1] for ex in extrema])

        if max_diff == 0:
            max_diff = 1

        scale = 255.0 / max_diff
        ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)

        # Calculate average brightness
        grayscale = ela_image.convert("L")
        pixels = list(grayscale.getdata())
        avg_brightness = sum(pixels) / len(pixels)

        if avg_brightness > 35:
            return {
                "ela_score": round(avg_brightness, 2),
                "ela_flag": True,
                "ela_reason": "ELA detected unusual compression differences in the image."
            }
        else:
            return {
                "ela_score": round(avg_brightness, 2),
                "ela_flag": False,
                "ela_reason": "ELA did not detect major compression inconsistencies."
            }

    except Exception as e:
        print("ELA ERROR:", e)
        return {
            "ela_score": 0,
            "ela_flag": False,
            "ela_reason": "ELA analysis could not be completed."
        }