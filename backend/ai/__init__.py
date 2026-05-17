import requests
from flask import current_app

def chat(model: str, messages: list, stream: bool = False, images: list = None):
    base_url = current_app.config["OLLAMA_BASE_URL"]
    payload = {"model": model, "messages": messages, "stream": stream}
    # images is a list of base64 strings; attach to the last message
    if images:
        payload["messages"] = messages[:-1] + [
            {**messages[-1], "images": images}
        ]
    response = requests.post(f"{base_url}/api/chat", json=payload, stream=stream)
    response.raise_for_status()
    return response
