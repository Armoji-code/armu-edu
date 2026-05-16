# MokyAI

A free, open source, self-hosted school platform. Replaces fragmented school software (diary systems, Google Classroom, messaging, grades, library) with a single unified platform that schools own and run themselves.

Licensed under **AGPL-3.0** — free to use, modify, and self-host. Distributions and hosted services must release source code.

## Stack

- **Backend**: Python + Flask + Flask-SocketIO
- **Database**: SQLite (small deployments) / PostgreSQL (larger)
- **AI**: Ollama (local inference, no cloud API costs) — OpenEuroLLM-Lithuanian by default
- **Frontend**: Vanilla JS (no framework)
- **Real-time**: WebSockets via Flask-SocketIO

## Getting started

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
python app.py
```

## Project structure

```
mokyai/
├── backend/        Flask app, API routes, models, AI, WebSocket handlers
├── frontend/       Vanilla JS frontend (src/ → dist/)
├── prototype/      mokyai-prototype.html — pixel-perfect design reference
├── docs/           Project documentation
├── requirements.txt
└── LICENSE
```

## Design reference

See `prototype/mokyai-prototype.html` — a complete single-file mockup of the entire student experience. All frontend work should match it as closely as possible.
