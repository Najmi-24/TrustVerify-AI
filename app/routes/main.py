from flask import Blueprint, render_template, request, jsonify, session, redirect, send_from_directory
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime, timedelta

from app.utils import analyze_file
from app.chatbot import answer_document_question
from app import db
from app.models import UploadHistory

main = Blueprint("main", __name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@main.route("/")
def home():
    history_all = UploadHistory.query.order_by(UploadHistory.created_at.desc()).all()

    seen = set()
    history = []

    for item in history_all:
        if item.filename not in seen:
            history.append(item)
            seen.add(item.filename)

        if len(history) == 5:
            break

    selected_document = session.get("document")

    return render_template(
        "index.html",
        history=history,
        document=selected_document,
        now=datetime.now(),
        timedelta=timedelta
    )


@main.route("/upload-chat", methods=["POST"])
def upload_chat():
    file = request.files.get("file")

    if not file or file.filename == "":
        return jsonify({"error": "Please choose a file first."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Please upload PDF, JPG, JPEG, or PNG."}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        file.save(save_path)
        result = analyze_file(save_path, filename)
    except Exception as e:
        print("UPLOAD ANALYSIS ERROR:", e)
        return jsonify({"error": "Document analysis failed. Please try another file."}), 500

    document = {
        "filename": filename,
        "doc_type": result.get("doc_type", "Document"),
        "summary": result.get("summary", result.get("source_text", "No summary available.")),
        "text": result.get("full_text", result.get("source_text", "")),
        "verdict": result.get("verdict", "Needs Review"),
        "confidence": result.get("confidence", "50%"),
        "reasons": result.get("reasons", []),
        "advice": "Please verify this document with the official source before trusting it."
    }

    session["document"] = document

    try:
        history_item = UploadHistory(
            filename=filename,
            summary=document["summary"],
            verdict=document["verdict"],
            confidence=document["confidence"],
            reasons=json.dumps(document["reasons"])
        )

        db.session.add(history_item)
        db.session.commit()

    except Exception as e:
        print("HISTORY SAVE ERROR:", e)

    return jsonify(document)


@main.route("/ask-document", methods=["POST"])
def ask_document():
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    print("USER QUESTION:", question)

    if not question:
        return jsonify({"answer": "Please type a question."})

    q = question.lower().strip()

    greetings = ["hi", "hello", "hey", "hii", "helo", "hai"]

    if q in greetings or q.startswith("hi ") or q.startswith("hello"):
        return jsonify({
            "answer": "👋 Hello! How can I help you today?"
        })

    if "how are you" in q:
        return jsonify({
            "answer": "😊 I'm doing great! How can I assist you?"
        })

    if "what can you do" in q:
        return jsonify({
            "answer": "📄 I can analyze documents, detect forgery, give summaries, and answer questions based on your uploaded file."
        })

    if "thank" in q:
        return jsonify({
            "answer": "😊 You're welcome! Let me know if you need anything else."
        })

    if q in ["bye", "goodbye", "see you"]:
        return jsonify({
            "answer": "👋 Goodbye! Have a great day."
        })

    document = session.get("document")

    if not document:
        return jsonify({
            "answer": "📄 Please upload a document first. Then I can answer questions about it."
        })

    try:
        answer = answer_document_question(question, document)
    except Exception as e:
        print("CHATBOT ERROR:", e)
        answer = "AI answer failed. Please try again."

    return jsonify({"answer": answer})


@main.route("/clear-session", methods=["POST"])
def clear_session():
    session.pop("document", None)
    return jsonify({"status": "cleared"})


@main.route("/load-history/<int:id>")
def load_history(id):
    item = UploadHistory.query.get(id)

    if not item:
        return jsonify({"error": "History item not found."}), 404

    document = {
        "filename": item.filename,
        "doc_type": "Document",
        "summary": item.summary,
        "text": item.summary,
        "verdict": item.verdict,
        "confidence": item.confidence,
        "reasons": json.loads(item.reasons) if item.reasons else []
    }

    session["document"] = document
    return jsonify(document)


@main.route("/open-chat/<int:id>")
def open_chat(id):
    item = UploadHistory.query.get(id)

    if item:
        session["document"] = {
            "filename": item.filename,
            "doc_type": "Document",
            "summary": item.summary,
            "text": item.summary,
            "verdict": item.verdict,
            "confidence": item.confidence,
            "reasons": json.loads(item.reasons) if item.reasons else []
        }

    return redirect("/")
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
from reportlab.lib.pagesizes import A4

@main.route("/download-report")
def download_report():
    document = session.get("document")

    if not document:
        return "No document available. Please upload first."

    file_path = os.path.join(UPLOAD_FOLDER, "TrustVerify_Report.pdf")

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    title_style.textColor = "#7c5cff"

    heading_style = styles["Heading2"]
    heading_style.textColor = "#111827"

    normal_style = styles["Normal"]
    normal_style.fontSize = 10
    normal_style.leading = 14

    content = []

    content.append(Paragraph("TrustVerify AI", title_style))
    content.append(Paragraph("Document Verification Report", styles["Heading2"]))
    content.append(Spacer(1, 18))

    content.append(Paragraph("<b>File Name:</b> " + str(document.get("filename", "-")), normal_style))
    content.append(Paragraph("<b>Document Type:</b> " + str(document.get("doc_type", "-")), normal_style))
    content.append(Paragraph("<b>Verdict:</b> " + str(document.get("verdict", "-")), normal_style))
    content.append(Paragraph("<b>Confidence:</b> " + str(document.get("confidence", "-")), normal_style))
    content.append(Spacer(1, 14))

    content.append(Paragraph("Summary", heading_style))
    content.append(Paragraph(str(document.get("summary", "No summary available.")), normal_style))
    content.append(Spacer(1, 14))

    content.append(Paragraph("Reasons", heading_style))

    reasons = document.get("reasons", [])
    if reasons:
        for reason in reasons:
            content.append(Paragraph("- " + str(reason), normal_style))
    else:
        content.append(Paragraph("- No reasons available.", normal_style))

    content.append(Spacer(1, 18))
    content.append(Paragraph(
        "<b>Note:</b> This report is AI-assisted. Please verify important documents with official sources.",
        normal_style
    ))

    doc.build(content)

    return send_file(file_path, as_attachment=True)


@main.route("/chat")
def chat():
    return render_template("chat.html")