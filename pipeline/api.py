"""Claude API client using httpx."""
import httpx
import json
import time

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"


class ClaudeAPIError(Exception):
    pass


class ClaudeClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key
        self.model = model

    @property
    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def generate(self, prompt: str, max_tokens: int = 4096, retries: int = 3) -> str:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        last_error = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(
                        CLAUDE_API_URL, headers=self._headers, json=payload
                    )
                    response.raise_for_status()
                    return response.json()["content"][0]["text"]
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (429, 529) and attempt < retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                body = e.response.text[:300]
                raise ClaudeAPIError(f"HTTP {e.response.status_code}: {body}") from e
            except httpx.RequestError as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise ClaudeAPIError(f"Network error: {e}") from e
        raise ClaudeAPIError(f"All {retries} attempts failed: {last_error}")

    def generate_json(self, prompt: str, max_tokens: int = 4096) -> dict:
        full_prompt = (
            prompt + "\n\nReturn ONLY valid JSON — no markdown fences, no commentary."
        )
        text = self.generate(full_prompt, max_tokens).strip()
        if text.startswith("```"):
            lines = text.split("\n")
            end = next(
                (i for i in range(len(lines) - 1, 0, -1) if lines[i].strip() == "```"),
                len(lines),
            )
            text = "\n".join(lines[1:end])
        return json.loads(text)
