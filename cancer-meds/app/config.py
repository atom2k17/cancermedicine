import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    # SQLite default for dev:
    basedir = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.abspath(os.path.join(basedir, '..', 'site.db'))

    #SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
    #"sqlite:///" + os.path.join(basedir, "..", "site.db")
    #SQLALCHEMY_DATABASE_URI = "C:/myproj/cancer-meds/site.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mail: configure for production (SendGrid/SES) via env vars
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 25))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "False") == "True"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@cancermeds.org")