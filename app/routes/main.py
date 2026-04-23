from flask import Blueprint, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import json
from app.utils import analyze_file
from app import db
from app.models import UploadHistory

main = Blueprint("main", __name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")


@main.route("/", methods=["GET", "POST"])
def home():
    history = UploadHistory.query.order_by(UploadHistory.created_at.desc()).limit(4).all()

    if request.method == "POST":
        file = request.files.get("file")

        if file and file.filename != "":
            filename = secure_filename(file.filename)
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(save_path)

            result = analyze_file(save_path, filename)

            history_item = UploadHistory(
                filename=filename,
                summary=result["source_text"],
                verdict=result["verdict"],
                confidence=result["confidence"],
                reasons=json.dumps(result["reasons"])
            )
            db.session.add(history_item)
            db.session.commit()

            history = UploadHistory.query.order_by(UploadHistory.created_at.desc()).limit(4).all()

            return render_template(
                "index.html",
                filename=filename,
                source_text=result["source_text"],
                verdict=result["verdict"],
                confidence=result["confidence"],
                reasons=result["reasons"],
                history=history,
                fact_text=None,
                fact_summary=None,
                fact_verdict=None,
                fact_confidence=None,
                fact_reasons=[],
                fact_error=None
            )

    return render_template(
        "index.html",
        filename=None,
        source_text=None,
        verdict=None,
        confidence=None,
        reasons=[],
        history=history,
        fact_text=None,
        fact_summary=None,
        fact_verdict=None,
        fact_confidence=None,
        fact_reasons=[],
        fact_error=None
    )


@main.route("/fact-check", methods=["POST"])
def fact_check():
    history = UploadHistory.query.order_by(UploadHistory.created_at.desc()).limit(4).all()
    text = request.form.get("fact_text", "").strip()

    if not text:
        return render_template(
            "index.html",
            filename=None,
            source_text=None,
            verdict=None,
            confidence=None,
            reasons=[],
            history=history,
            fact_text="",
            fact_summary=None,
            fact_verdict=None,
            fact_confidence=None,
            fact_reasons=[],
            fact_error="Please enter text to analyze."
        )

    lower = text.lower()
    reasons = []

    if "shocking" in lower or "breaking" in lower:
        reasons.append("The text uses sensational language.")

    if "100% guarantee" in lower or "no risk" in lower:
        reasons.append("The text contains exaggerated claims.")

    if len(text.split()) < 10:
        reasons.append("The text is too short for reliable analysis.")

    if "unknown source" in lower or "forwarded" in lower:
        reasons.append("The content appears to lack a reliable source.")

    if len(reasons) == 0:
        fact_verdict = "Likely Real"
        fact_confidence = "85%"
        reasons = ["No major suspicious patterns detected."]
    elif len(reasons) == 1:
        fact_verdict = "Suspicious"
        fact_confidence = "70%"
    else:
        fact_verdict = "Likely Fake"
        fact_confidence = "80%"

    fact_summary = text[:200] + "..." if len(text) > 200 else text

    return render_template(
        "index.html",
        filename=None,
        source_text=None,
        verdict=None,
        confidence=None,
        reasons=[],
        history=history,
        fact_text=text,
        fact_summary=fact_summary,
        fact_verdict=fact_verdict,
        fact_confidence=fact_confidence,
        fact_reasons=reasons,
        fact_error=None
    )


@main.route("/assistant", methods=["POST"])
def assistant():
    data = request.get_json()

    message = data.get("message", "").lower()
    filename = data.get("filename", "")
    verdict = data.get("verdict", "")
    confidence = data.get("confidence", "")
    source_text = data.get("source_text", "")
    reasons = data.get("reasons", [])

    if "my file" in message or "uploaded file" in message:
        if filename:
            reply = f"You uploaded: {filename}"
        else:
            reply = "No file has been uploaded yet."

    elif "verdict" in message or "result" in message:
        if verdict:
            reply = f"The current verdict is {verdict} with confidence {confidence}."
        else:
            reply = "No analysis result is available yet."

    elif "confidence" in message:
        if confidence:
            reply = f"The confidence score is {confidence}."
        else:
            reply = "No confidence score is available."

    elif "summary" in message:
        if source_text:
            reply = f"Summary: {source_text}"
        else:
            reply = "No summary available yet."

    elif "why" in message and ("flagged" in message or "suspicious" in message or "tampered" in message):
        if reasons:
            reply = "Your file was flagged because: " + "; ".join(reasons)
        else:
            reply = "No analysis reasons are available yet."

    elif "upload" in message:
        reply = "You can upload JPG, PNG, JPEG, PDF, TXT, and DOCX files."

    elif "file type" in message or "supported" in message:
        reply = "Supported file types are JPG, PNG, JPEG, PDF, TXT, and DOCX."

    elif "fake" in message or "real" in message:
        reply = "The system classifies files as Likely Genuine, Suspicious, Likely Tampered, or Needs Review."

    elif "suspicious" in message:
        reply = "Suspicious means unusual patterns were found, but not enough to confirm tampering."

    elif "tampered" in message:
        reply = "Likely Tampered means stronger suspicious signs were found that suggest the file may have been edited or modified."

    elif "genuine" in message:
        reply = "Likely Genuine means the uploaded file appears normal based on the current checks."

    elif "how" in message:
        reply = "The system uploads your file, extracts text, generates a summary, analyzes patterns, and returns a verdict with reasons."

    elif "history" in message:
        reply = "The History section shows your previously uploaded files and their analysis results."

    else:
        reply = "I can help explain your uploaded file, summary, verdict, confidence, reasons, supported file types, and how the system works."

    return jsonify({"reply": reply})