#!/usr/bin/env bash
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
G='\033[0;32m'; B='\033[0;34m'; Y='\033[0;33m'; R='\033[0;31m'; W='\033[0m'
BOLD='\033[1m'

hr()  { printf "${B}────────────────────────────────────────────────────────${W}\n"; }
ok()  { printf "  ${G}✓${W} %s\n" "$*"; }
inf() { printf "  ${B}·${W} %s\n" "$*"; }
ask() { printf "  ${Y}?${W} %s " "$*"; }
err() { printf "  ${R}✗${W} %s\n" "$*" >&2; }

clear
printf "\n${BOLD}${G}  Armu — Setup${W}\n\n"
hr
printf "  This script will:\n"
printf "    1. Create a Python virtual environment and install dependencies\n"
printf "    2. Generate a secure secret key\n"
printf "    3. Configure the AI provider\n"
printf "    4. Initialise the database\n"
printf "    5. Optionally load demo accounts\n"
hr
printf "\n"

# ── Prerequisites ─────────────────────────────────────────────────────────────
inf "Checking prerequisites…"

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null)
        if [[ "$ver" == "True" ]]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    err "Python 3.10+ is required but was not found."
    err "Install it from https://python.org and re-run this script."
    exit 1
fi
ok "Python: $($PYTHON --version)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$SCRIPT_DIR/backend"
VENV="$SCRIPT_DIR/.venv"
ENV_FILE="$BACKEND/.env"
FLASK="$VENV/bin/flask"
PYTHON_VENV="$VENV/bin/python"

# ── Virtual environment ───────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}1. Dependencies${W}\n"
hr

if [[ -d "$VENV" ]]; then
    inf "Virtual environment already exists — skipping creation."
else
    inf "Creating virtual environment…"
    "$PYTHON" -m venv "$VENV"
    ok "Virtual environment created at .venv/"
fi

inf "Installing Python packages…"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
ok "All packages installed."

# ── .env ─────────────────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}2. Configuration${W}\n"
hr

if [[ -f "$ENV_FILE" ]]; then
    inf ".env already exists — skipping generation."
else
    cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
    SECRET=$("$PYTHON_VENV" -c "import secrets; print(secrets.token_hex(32))")
    # Replace the placeholder key
    sed -i "s|SECRET_KEY=change-me-in-production|SECRET_KEY=${SECRET}|" "$ENV_FILE"
    ok "Generated .env with a random SECRET_KEY."
fi

# ── AI provider ───────────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}3. AI Provider${W}\n"
hr
printf "  Armu supports three AI backends:\n\n"
printf "    ${G}1${W}) Ollama   — local inference, no API costs (recommended)\n"
printf "    ${G}2${W}) OpenAI   — GPT-4o and friends (API key required)\n"
printf "    ${G}3${W}) Anthropic — Claude models (API key required)\n\n"
ask "Choose provider [1/2/3, default: 1]:"
read -r PROVIDER_CHOICE
PROVIDER_CHOICE="${PROVIDER_CHOICE:-1}"

case "$PROVIDER_CHOICE" in
    2)
        PROVIDER="openai"
        printf "\n"
        ask "OpenAI API key (sk-...):"
        read -r -s API_KEY; echo
        ask "Custom base URL? (leave blank for api.openai.com):"
        read -r BASE_URL
        ask "Tutor model [default: gpt-4o-mini]:"
        read -r TUTOR_MODEL; TUTOR_MODEL="${TUTOR_MODEL:-gpt-4o-mini}"
        ask "Advanced model [default: gpt-4o]:"
        read -r ADV_MODEL; ADV_MODEL="${ADV_MODEL:-gpt-4o}"
        ask "Tracker model (digests/nudges) [default: gpt-4o-mini]:"
        read -r TRACK_MODEL; TRACK_MODEL="${TRACK_MODEL:-gpt-4o-mini}"

        sed -i "s|AI_PROVIDER=ollama|AI_PROVIDER=openai|" "$ENV_FILE"
        ok "AI provider set to OpenAI."
        ;;
    3)
        PROVIDER="anthropic"
        printf "\n"
        ask "Anthropic API key (sk-ant-...):"
        read -r -s API_KEY; echo
        ask "Tutor model [default: claude-haiku-4-5-20251001]:"
        read -r TUTOR_MODEL; TUTOR_MODEL="${TUTOR_MODEL:-claude-haiku-4-5-20251001}"
        ask "Advanced model [default: claude-sonnet-4-6]:"
        read -r ADV_MODEL; ADV_MODEL="${ADV_MODEL:-claude-sonnet-4-6}"
        ask "Tracker model [default: claude-haiku-4-5-20251001]:"
        read -r TRACK_MODEL; TRACK_MODEL="${TRACK_MODEL:-claude-haiku-4-5-20251001}"

        sed -i "s|AI_PROVIDER=ollama|AI_PROVIDER=anthropic|" "$ENV_FILE"
        ok "AI provider set to Anthropic."
        ;;
    *)
        PROVIDER="ollama"
        printf "\n"
        printf "  Ollama model presets:\n\n"
        printf "    ${G}1${W}) Lightweight  — llama3.2:3b for everything   (~2 GB VRAM)\n"
        printf "    ${G}2${W}) Balanced     — gemma3:12b tutor + llama3.2:3b tracker   (~10 GB VRAM)\n"
        printf "    ${G}3${W}) Custom       — enter model names manually\n\n"
        ask "Choose preset [1/2/3, default: 2]:"
        read -r MODEL_PRESET
        MODEL_PRESET="${MODEL_PRESET:-2}"

        case "$MODEL_PRESET" in
            1)
                TUTOR_MODEL="llama3.2:3b"
                ADV_MODEL="llama3.2:3b"
                TRACK_MODEL="llama3.2:3b"
                ;;
            3)
                ask "Tutor model [default: gemma3:12b]:"
                read -r TUTOR_MODEL; TUTOR_MODEL="${TUTOR_MODEL:-gemma3:12b}"
                ask "Advanced model [default: gemma3:12b]:"
                read -r ADV_MODEL; ADV_MODEL="${ADV_MODEL:-gemma3:12b}"
                ask "Tracker model (digests/nudges) [default: llama3.2:3b]:"
                read -r TRACK_MODEL; TRACK_MODEL="${TRACK_MODEL:-llama3.2:3b}"
                ;;
            *)
                TUTOR_MODEL="gemma3:12b"
                ADV_MODEL="gemma3:12b"
                TRACK_MODEL="llama3.2:3b"
                ;;
        esac

        sed -i "s|OLLAMA_TUTOR_MODEL=gemma3:12b|OLLAMA_TUTOR_MODEL=${TUTOR_MODEL}|" "$ENV_FILE"
        sed -i "s|OLLAMA_ADVANCED_MODEL=gemma3:12b|OLLAMA_ADVANCED_MODEL=${ADV_MODEL}|" "$ENV_FILE"
        sed -i "s|OLLAMA_TRACKER_MODEL=llama3.2:3b|OLLAMA_TRACKER_MODEL=${TRACK_MODEL}|" "$ENV_FILE"

        if ! command -v ollama &>/dev/null; then
            printf "\n"
            printf "  ${Y}!${W} Ollama is not installed or not in PATH.\n"
            printf "    Install it from ${B}https://ollama.com${W} then run:\n\n"
            printf "      ollama pull ${TUTOR_MODEL}\n"
            [[ "$TRACK_MODEL" != "$TUTOR_MODEL" ]] && printf "      ollama pull ${TRACK_MODEL}\n"
            printf "\n"
        else
            ok "Ollama found: $(ollama --version 2>/dev/null | head -1)"
            printf "\n"

            MODELS_TO_PULL=("$TRACK_MODEL")
            [[ "$TUTOR_MODEL" != "$TRACK_MODEL" ]] && MODELS_TO_PULL+=("$TUTOR_MODEL")

            ask "Pull selected models now? This may take a while. [Y/n]:"
            read -r PULL_NOW
            if [[ "${PULL_NOW:-Y}" =~ ^[Yy]$ ]]; then
                for MODEL in "${MODELS_TO_PULL[@]}"; do
                    inf "Pulling ${MODEL}…"
                    ollama pull "$MODEL"
                    ok "Pulled ${MODEL}."
                done
            else
                inf "Skipped — pull models later with:"
                for MODEL in "${MODELS_TO_PULL[@]}"; do
                    printf "    ollama pull %s\n" "$MODEL"
                done
            fi
        fi
        ok "AI provider set to Ollama."
        ;;
esac

# Write API key and model names into .env for API providers
if [[ "$PROVIDER" == "openai" || "$PROVIDER" == "anthropic" ]]; then
    {
        echo ""
        echo "# Written by setup.sh"
        [[ -n "${API_KEY:-}" ]] && echo "AI_API_KEY=${API_KEY}"
        [[ -n "${BASE_URL:-}" ]] && echo "AI_API_BASE_URL=${BASE_URL}"
    } >> "$ENV_FILE"
fi

# Write model names for all providers
{
    echo "TUTOR_MODEL=${TUTOR_MODEL}"
    echo "ADV_MODEL=${ADV_MODEL}"
    echo "TRACKER_MODEL=${TRACK_MODEL}"
} >> "$ENV_FILE"

# ── TURN server (optional) ───────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}4. Video Calls (TURN server)${W}\n"
hr
printf "  Video calls use WebRTC with Google STUN by default — this works on most\n"
printf "  school networks. For calls over home WiFi (symmetric NAT), a TURN relay\n"
printf "  server is needed. You can configure one later in Admin → Settings.\n\n"
ask "Configure a TURN server now? [y/N]:"
read -r TURN_CHOICE
if [[ "${TURN_CHOICE:-N}" =~ ^[Yy]$ ]]; then
    ask "  TURN URL (e.g. turn:your-server.com:3478):"
    read -r TURN_URL
    ask "  TURN username:"
    read -r TURN_USERNAME
    ask "  TURN credential (password):"
    read -r -s TURN_CREDENTIAL
    printf "\n"
    {
        echo ""
        echo "# TURN server for video calls"
        [[ -n "${TURN_URL:-}" ]]        && echo "TURN_URL=${TURN_URL}"
        [[ -n "${TURN_USERNAME:-}" ]]   && echo "TURN_USERNAME=${TURN_USERNAME}"
        [[ -n "${TURN_CREDENTIAL:-}" ]] && echo "TURN_CREDENTIAL=${TURN_CREDENTIAL}"
    } >> "$ENV_FILE"
    ok "TURN server saved to .env."
else
    inf "Skipped. Configure TURN later in Admin → Settings → Video Call."
fi

# ── Database ──────────────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}5. Database${W}\n"
hr
inf "Running database migrations…"
if ! (cd "$BACKEND" && FLASK_APP=app.py "$FLASK" db upgrade 2>&1 | grep -v "UserWarning\|app = app_factory"); then
    err "Database migration failed. Check the output above."
    exit 1
fi
ok "Database ready."

# ── Admin account ─────────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}6. Admin account${W}\n"
hr
printf "  Create the admin account you will use to log in and manage the school.\n\n"
ask "Admin name [default: Admin]:"
read -r ADMIN_NAME; ADMIN_NAME="${ADMIN_NAME:-Admin}"
ask "Admin email:"
read -r ADMIN_EMAIL
while [[ -z "$ADMIN_EMAIL" ]]; do
    err "Email is required."
    ask "Admin email:"
    read -r ADMIN_EMAIL
done
ask "Admin password (min 8 characters):"
read -r -s ADMIN_PASSWORD; echo
while [[ ${#ADMIN_PASSWORD} -lt 8 ]]; do
    err "Password must be at least 8 characters."
    ask "Admin password:"
    read -r -s ADMIN_PASSWORD; echo
done
ask "School name [default: My School]:"
read -r SCHOOL_NAME; SCHOOL_NAME="${SCHOOL_NAME:-My School}"

"$PYTHON_VENV" - <<PYEOF
import sys, os
sys.path.insert(0, '$BACKEND')
os.chdir('$BACKEND')
from app import create_app
from models import db
from models.user import User
from models.school import School

app = create_app()
with app.app_context():
    if School.query.first():
        print("School already exists — skipping admin creation.")
        sys.exit(0)
    school = School(name=${SCHOOL_NAME@Q})
    db.session.add(school)
    db.session.flush()
    admin = User(name=${ADMIN_NAME@Q}, email=${ADMIN_EMAIL@Q}, role="admin", school_id=school.id)
    admin.set_password(${ADMIN_PASSWORD@Q})
    db.session.add(admin)
    db.session.commit()
    print("Admin account created.")
PYEOF
ok "Admin account ready — log in with: $ADMIN_EMAIL"

# ── Demo accounts ─────────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}7. Demo accounts (optional)${W}\n"
hr
printf "  Adds sample students, teachers, classes, and assignments for testing.\n\n"
ask "Create demo accounts? [y/N]:"
read -r SEED_CHOICE
if [[ "${SEED_CHOICE:-N}" =~ ^[Yy]$ ]]; then
    (cd "$BACKEND" && "$PYTHON_VENV" seed.py 2>&1 | grep -v UserWarning | grep -v "app = app_factory" || true)
    ok "Demo accounts created (admin@test.com, teacher@test.com, student@test.com / password)."
else
    inf "Skipped. You can seed later with: cd backend && python seed.py"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
printf "\n"
hr
printf "  ${BOLD}${G}Setup complete!${W}\n"
hr
printf "\n"
printf "  Start Armu:\n\n"
printf "    ${BOLD}cd backend${W}\n"
printf "    ${BOLD}python app.py${W}\n\n"
printf "  Then open ${B}http://localhost:5000${W} in your browser.\n\n"
printf "  To change AI settings later, log in as admin and go to\n"
printf "  ${B}Admin → Settings → AI Configuration${W}.\n\n"
