# MokyAI

A free, open source, self-hosted school platform. Replaces fragmented school software (diary systems, Google Classroom, messaging, grades, library) with a single unified platform that schools own and run themselves.

Licensed under **AGPL-3.0** — free to use, modify, and self-host. Distributions and hosted services must release source code.

## Stack

- **Backend**: Python + Flask + Flask-SocketIO
- **Database**: SQLite (small deployments) / PostgreSQL (larger)
- **AI**: Pluggable — Ollama (local, no API costs), OpenAI, or Anthropic; configured per-school via the admin panel
- **Frontend**: Vanilla JS (no framework)
- **Real-time**: WebSockets via Flask-SocketIO

## Getting started

```bash
# 1. Clone and set up the environment
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r ../requirements.txt

# 2. Configure (copy and edit the example)
cp ../.env.example .env
#    At minimum, set SECRET_KEY to a random value:
#    python -c "import secrets; print(secrets.token_hex(32))"

# 3. Initialise the database
flask --app app db upgrade

# 4. (Optional) seed demo data
python seed.py

# 5. Run
python app.py
```

The app starts at **http://localhost:5000**.

## AI setup

By default MokyAI uses **Ollama** for local inference (no API costs).

```bash
# Install Ollama: https://ollama.com
ollama pull gemma3:12b      # tutor + advanced model
ollama pull llama3.2:3b     # tracker model (digests, nudges, auto-title)
```

To switch to OpenAI or Anthropic, go to **Admin → Settings → AI Configuration** after logging in — no restart required.

## Project structure

```
mokyai/
├── backend/        Flask app, API routes, models, AI, WebSocket handlers
│   ├── ai/         Multi-provider AI abstraction (Ollama / OpenAI / Anthropic)
│   ├── api/        REST API blueprints
│   ├── models/     SQLAlchemy models
│   └── static/     Served at /static/ (notif.js)
├── frontend/       Vanilla JS frontend pages
├── prototype/      mokyai-prototype.html — pixel-perfect design reference
├── docs/           Project documentation
├── .env.example    Environment variable template
├── requirements.txt
└── LICENSE
```

## Environment variables

Copy `.env.example` to `backend/.env`. Key variables:

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(insecure default)* | **Required** — set a random secret before deploying |
| `DATABASE_URL` | SQLite at repo root | PostgreSQL URL for production |
| `FLASK_DEBUG` | `0` | Set to `1` for local development only |
| `CORS_ORIGINS` | `http://localhost:5000` | Allowed CORS / WebSocket origins |
| `AI_PROVIDER` | `ollama` | `ollama` \| `openai` \| `anthropic` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |

All AI settings can also be changed at runtime via Admin → Settings.
