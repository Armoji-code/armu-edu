import requests
from flask import current_app

def chat(model: str, messages: list, stream: bool = False):
    base_url = current_app.config["OLLAMA_BASE_URL"]
    payload = {"model": model, "messages": messages, "stream": stream}
    response = requests.post(f"{base_url}/api/chat", json=payload, stream=stream)
    response.raise_for_status()
    return response
