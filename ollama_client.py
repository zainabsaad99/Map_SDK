# ==========================
# File: ollama_client.py
# ==========================
import requests

class OllamaClient:
    def __init__(self, model="llama3"):
        self.model = model
        self.url = "http://localhost:11434/api/chat"

    def chat(self, messages):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        response = requests.post(self.url, json=payload)
        response.raise_for_status()
        data = response.json()

        # Ollama returns: {"message": {"role": "...", "content": "..."}}
        return data["message"]["content"]
