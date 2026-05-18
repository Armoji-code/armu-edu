import json
import requests
from flask import current_app


def get_ai_config():
    """Build AI config from School.settings with env/config fallbacks."""
    s = {}
    try:
        from models.school import School
        school = School.query.first()
        if school:
            s = school.settings or {}
    except Exception:
        pass
    cfg = current_app.config
    return {
        'provider':            s.get('ai_provider', cfg.get('AI_PROVIDER', 'ollama')),
        'ollama_base_url':     s.get('ollama_base_url', cfg.get('OLLAMA_BASE_URL', 'http://localhost:11434')),
        'api_key':             s.get('ai_api_key', ''),
        'api_base_url':        s.get('ai_api_base_url', ''),
        'tutor_model':         s.get('tutor_model', s.get('ollama_tutor_model',
                                   cfg.get('OLLAMA_TUTOR_MODEL', 'gemma3:12b'))),
        'advanced_model':      s.get('advanced_model', s.get('ollama_advanced_model',
                                   cfg.get('OLLAMA_ADVANCED_MODEL', 'gemma3:12b'))),
        'tracker_model':       s.get('tracker_model', s.get('ollama_tracker_model',
                                   cfg.get('OLLAMA_TRACKER_MODEL', 'llama3.2:3b'))),
        'tutor_temperature':   float(s.get('tutor_temperature', 0.7)),
        'tracker_temperature': float(s.get('tracker_temperature', 0.3)),
        'tutor_top_p':         float(s.get('tutor_top_p', 1.0)),
        'max_tokens':          int(s.get('max_tokens', 2048)),
        'tutor_system_prompt': s.get('tutor_system_prompt', ''),
    }


def stream(model: str, messages: list, temperature: float = None,
           top_p: float = None, max_tokens: int = None, images: list = None):
    """Generator yielding text tokens from the configured AI provider."""
    cfg = get_ai_config()
    provider = cfg['provider']
    if provider == 'openai':
        yield from _stream_openai(model, messages, temperature, top_p, max_tokens,
                                  images, cfg['api_key'], cfg['api_base_url'])
    elif provider == 'anthropic':
        yield from _stream_anthropic(model, messages, temperature, top_p, max_tokens, cfg['api_key'])
    else:
        yield from _stream_ollama(model, messages, temperature, top_p, images, cfg['ollama_base_url'])


def complete(model: str, messages: list, temperature: float = None,
             top_p: float = None, max_tokens: int = None):
    """Non-streaming: return full response text."""
    cfg = get_ai_config()
    provider = cfg['provider']
    if provider == 'openai':
        return _complete_openai(model, messages, temperature, top_p, max_tokens,
                                cfg['api_key'], cfg['api_base_url'])
    elif provider == 'anthropic':
        return _complete_anthropic(model, messages, temperature, top_p, max_tokens, cfg['api_key'])
    else:
        return _complete_ollama(model, messages, temperature, top_p, cfg['ollama_base_url'])


# ── Ollama ────────────────────────────────────────────────────────────────────

def _ollama_payload(model, messages, stream, temperature, top_p, images):
    payload = {"model": model, "messages": messages, "stream": stream}
    options = {}
    if temperature is not None:
        options["temperature"] = temperature
    if top_p is not None:
        options["top_p"] = top_p
    if options:
        payload["options"] = options
    if images:
        payload["messages"] = messages[:-1] + [{**messages[-1], "images": images}]
    return payload


def _stream_ollama(model, messages, temperature, top_p, images, base_url):
    resp = requests.post(f"{base_url}/api/chat",
                         json=_ollama_payload(model, messages, True, temperature, top_p, images),
                         stream=True, timeout=120)
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            continue
        token = chunk.get("message", {}).get("content", "")
        if token:
            yield token
        if chunk.get("done"):
            break


def _complete_ollama(model, messages, temperature, top_p, base_url):
    resp = requests.post(f"{base_url}/api/chat",
                         json=_ollama_payload(model, messages, False, temperature, top_p, None),
                         timeout=120)
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "")


# ── OpenAI (and OpenAI-compatible) ────────────────────────────────────────────

def _openai_headers(api_key):
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _openai_messages(messages, images):
    if not images:
        return messages
    last = messages[-1]
    content = [{"type": "text", "text": last["content"]}]
    for img in images:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
    return messages[:-1] + [{"role": last["role"], "content": content}]


def _openai_payload(model, messages, stream, temperature, top_p, max_tokens, images):
    payload = {"model": model, "messages": _openai_messages(messages, images), "stream": stream}
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def _stream_openai(model, messages, temperature, top_p, max_tokens, images, api_key, base_url):
    url = (base_url or "https://api.openai.com/v1") + "/chat/completions"
    resp = requests.post(url, headers=_openai_headers(api_key),
                         json=_openai_payload(model, messages, True, temperature, top_p, max_tokens, images),
                         stream=True, timeout=120)
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line or line == b"data: [DONE]":
            continue
        if line.startswith(b"data: "):
            try:
                chunk = json.loads(line[6:])
                token = chunk["choices"][0]["delta"].get("content", "")
                if token:
                    yield token
            except (json.JSONDecodeError, KeyError, IndexError):
                continue


def _complete_openai(model, messages, temperature, top_p, max_tokens, api_key, base_url):
    url = (base_url or "https://api.openai.com/v1") + "/chat/completions"
    resp = requests.post(url, headers=_openai_headers(api_key),
                         json=_openai_payload(model, messages, False, temperature, top_p, max_tokens, None),
                         timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ── Anthropic ─────────────────────────────────────────────────────────────────

def _anthropic_headers(api_key):
    return {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}


def _anthropic_payload(model, messages, stream, temperature, top_p, max_tokens):
    sys_content = "\n".join(m["content"] for m in messages if m["role"] == "system")
    user_msgs = [m for m in messages if m["role"] != "system"]
    payload = {"model": model, "messages": user_msgs, "max_tokens": max_tokens or 2048, "stream": stream}
    if sys_content:
        payload["system"] = sys_content
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    return payload


def _stream_anthropic(model, messages, temperature, top_p, max_tokens, api_key):
    resp = requests.post("https://api.anthropic.com/v1/messages",
                         headers=_anthropic_headers(api_key),
                         json=_anthropic_payload(model, messages, True, temperature, top_p, max_tokens),
                         stream=True, timeout=120)
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line or not line.startswith(b"data: "):
            continue
        try:
            chunk = json.loads(line[6:])
            if chunk.get("type") == "content_block_delta":
                token = chunk.get("delta", {}).get("text", "")
                if token:
                    yield token
        except (json.JSONDecodeError, KeyError):
            continue


def _complete_anthropic(model, messages, temperature, top_p, max_tokens, api_key):
    resp = requests.post("https://api.anthropic.com/v1/messages",
                         headers=_anthropic_headers(api_key),
                         json=_anthropic_payload(model, messages, False, temperature, top_p, max_tokens),
                         timeout=120)
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]
