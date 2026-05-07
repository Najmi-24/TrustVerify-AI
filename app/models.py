from app import db
from datetime import datetime

class UploadHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    verdict = db.Column(db.String(100), nullable=True)
    confidence = db.Column(db.String(50), nullable=True)
    reasons = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)