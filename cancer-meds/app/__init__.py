from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from .config import Config
import os

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'secret-key'
    app.config.from_object(Config)
    print("🔹 Using DB:", app.config["SQLALCHEMY_DATABASE_URI"])
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    mail.init_app(app)

    # Register blueprints or modules
    from app import models
    from .auth import auth_bp
    from .meds import meds_bp
    from .matches import matches_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(meds_bp)
    app.register_blueprint(matches_bp)

    # simple homepage route
    @app.route("/")
    def home():
        from .models import Medicine
        # show some available donations
        donations = Medicine.query.filter_by(type="donation", status="available").limit(8).all()
        return __import__("flask").render_template("index.html", donations=donations)

    return app