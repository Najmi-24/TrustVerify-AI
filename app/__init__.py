from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()   # 👈 VERY IMPORTANT (this was missing or wrong)


def create_app():
    app = Flask(__name__)

    app.config["UPLOAD_FOLDER"] = "uploads"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///history.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from app.routes.main import main
    app.register_blueprint(main)

    with app.app_context():
        from app.models import UploadHistory
        db.create_all()

    return app