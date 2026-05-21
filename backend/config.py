import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

_DEFAULT_SECRET = "change-me-in-production"

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", _DEFAULT_SECRET)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, '..', 'armu.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEBUG        = os.environ.get("FLASK_DEBUG", "0") == "1"
    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5000").split(",")]

    TURN_URL        = os.environ.get("TURN_URL",        "")
    TURN_USERNAME   = os.environ.get("TURN_USERNAME",   "")
    TURN_CREDENTIAL = os.environ.get("TURN_CREDENTIAL", "")

    AI_PROVIDER           = os.environ.get("AI_PROVIDER",           "ollama")
    OLLAMA_BASE_URL       = os.environ.get("OLLAMA_BASE_URL",       "http://localhost:11434")
    OLLAMA_TRACKER_MODEL  = os.environ.get("OLLAMA_TRACKER_MODEL",  "llama3.2:3b")
    OLLAMA_TUTOR_MODEL    = os.environ.get("OLLAMA_TUTOR_MODEL",    "gemma3:12b")
    OLLAMA_ADVANCED_MODEL = os.environ.get("OLLAMA_ADVANCED_MODEL", "gemma3:12b")
