import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, '..', 'mokyai.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    OLLAMA_BASE_URL       = os.environ.get("OLLAMA_BASE_URL",       "http://localhost:11434")
    OLLAMA_TRACKER_MODEL  = os.environ.get("OLLAMA_TRACKER_MODEL",  "llama3.2:3b")
    OLLAMA_TUTOR_MODEL    = os.environ.get("OLLAMA_TUTOR_MODEL",    "qwen2.5vl:7b")
    OLLAMA_ADVANCED_MODEL = os.environ.get("OLLAMA_ADVANCED_MODEL", "qwen2.5vl:7b")
