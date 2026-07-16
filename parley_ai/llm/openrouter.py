import httpx
import json
import os
import time
from dotenv import load_dotenv
from parley_ai.llm.base import LLMClient

load_dotenv()

class OpenRouterClient(LLMClient):
    def __init__(self, model: str = "google/gemma-2-9b-it:free", base_url: str | None = None) -> None:
        super().__init__()
        self.model = "meta-llama/llama-3.3-70b-instruct:free"
        
        # Load from environment variable (do not hardcode keys)
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def chat(self, system: str, messages: list[dict], json_mode: bool = False, temperature: float = 0.7) -> str:
        # Hardcode the active free model
        self.model = "meta-llama/llama-3.3-70b-instruct:free"
        
        formatted_messages = [{"role": "system", "content": system}] + messages
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "ParleyLabLocal"
        }

        # Auto-Retry Loop for Free-Tier Limits
        max_retries = 3
        for attempt in range(max_retries):
            with httpx.Client() as client:
                response = client.post(
                    self.url,
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )
                
                # Catch the upstream rate limit
                if response.status_code == 429:
                    print(f"OPENROUTER 429: Rate limited upstream. Retrying in 5 seconds... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(5)
                    continue 
                    
                # Catch any other errors
                if response.status_code != 200:
                    print(f"OPENROUTER ERROR: {response.status_code} - {response.text}")
                    response.raise_for_status()
                    
                # Success
                return response.json()["choices"]["message"]["content"]
        
        # If it fails all 3 times, crash loudly so it triggers the LLMRouter fallback
        response.raise_for_status()