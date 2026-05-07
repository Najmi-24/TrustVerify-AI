from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
load_dotenv()
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)

    app.secret_key = "trustverify_secret_key"

    app.config["UPLOAD_FOLDER"] = "uploads"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///history.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    db.init_app(app)

    from app.routes.main import main
    app.register_blueprint(main)

    with app.app_context():
        from app.models import UploadHistory
        db.create_all()

    return app