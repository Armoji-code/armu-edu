import json
import re
import threading
import requests

MODERATION_MODEL = "llama3.2:3b"
FLAG_THRESHOLD   = 0.5

_SYSTEM = (
    "You are a school message safety classifier. "
    "Detect bullying, harassment, threats, hate speech, or inappropriate content. "
    "Respond with ONLY valid JSON — no other text, no markdown:\n"
    '{"flag": false, "severity": 0.0, "reason": "safe"}\n'
    "severity: 0.0 = completely safe, 0.5 = borderline, 1.0 = severe threat/abuse. "
    "Set flag=true only when severity >= 0.5."
)


def _parse(text: str):
    """Extract JSON from model output, tolerating extra surrounding text."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{[^{}]+\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def scan_message(message_id: int, app):
    """Run in a background thread. Scans a message and stores flag if needed."""
    with app.app_context():
        try:
            from models import db
            from models.social import Message, FlaggedMessage
            from models.school import School

            msg = Message.query.get(message_id)
            if not msg:
                return

            # Check school setting
            sender = msg.sender
            if not sender:
                return
            school = School.query.get(sender.school_id)
            if not school:
                return
            settings = school.settings or {}
            if not settings.get("message_scan_enabled", False):
                return

            ollama_url = settings.get("ollama_base_url", "http://localhost:11434")

            payload = {
                "model": MODERATION_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user",   "content": f'Message: "{msg.content}"'},
                ],
                "stream": False,
                "options": {"temperature": 0.0},
            }
            resp = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=30)
            resp.raise_for_status()
            raw = resp.json().get("message", {}).get("content", "")
            data = _parse(raw)
            if not data:
                return

            severity = float(data.get("severity", 0.0))
            flagged  = bool(data.get("flag", False)) or severity >= FLAG_THRESHOLD
            if not flagged:
                return

            reason = str(data.get("reason", ""))[:500]
            flag = FlaggedMessage(
                message_id=message_id,
                severity=round(severity, 3),
                reason=reason,
                status="pending",
            )
            db.session.add(flag)
            db.session.commit()
        except Exception:
            pass  # scanning must never crash the app


def scan_async(message_id: int, app):
    """Fire-and-forget background scan."""
    t = threading.Thread(target=scan_message, args=(message_id, app), daemon=True)
    t.start()
