"""Local Ollama client with token tracking, retry logic, and health checking.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ModelUsageStats(BaseModel):
    provider: str = "Ollama (Local)"
    model: str = ""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retries: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_external_api_cost: float = 0.0


class OllamaClient:
    """Client for local Ollama API adhering to challenge specifications."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3.5:4B")
        self.stats = ModelUsageStats(model=self.model)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def check_health(self) -> Dict[str, Any]:
        """Verify server reachability and model availability."""
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", [])]
                    # Check if requested model matches any installed model
                    model_found = any(self.model in m or m.startswith(self.model) for m in models)
                    return {
                        "reachable": True,
                        "model_installed": model_found,
                        "available_models": models,
                        "error": None,
                    }
                else:
                    return {
                        "reachable": False,
                        "model_installed": False,
                        "error": f"HTTP status {resp.status}",
                    }
        except Exception as e:
            return {
                "reachable": False,
                "model_installed": False,
                "error": str(e),
            }

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """Send chat completion expecting JSON response, with caching and retries."""
        cache_key = f"{system_prompt}|||{user_prompt}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_ctx": 2048,
            },
        }

        url = f"{self.base_url}/api/chat"
        data = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries + 1):
            self.stats.total_calls += 1
            if attempt > 0:
                self.stats.retries += 1

            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status == 200:
                        res = json.loads(resp.read().decode("utf-8"))
                        # Record token usage from Ollama metadata
                        prompt_eval = res.get("prompt_eval_count", 0)
                        eval_cnt = res.get("eval_count", 0)
                        self.stats.input_tokens += prompt_eval
                        self.stats.output_tokens += eval_cnt
                        self.stats.successful_calls += 1

                        content = res.get("message", {}).get("content", "")
                        parsed = json.loads(content)
                        self._cache[cache_key] = parsed
                        return parsed
                    else:
                        if attempt == max_retries:
                            self.stats.failed_calls += 1
            except Exception as e:
                if attempt == max_retries:
                    self.stats.failed_calls += 1
                    return None
        return None

    def get_usage_summary(self) -> Dict[str, Any]:
        """Return structured summary of LLM usage and metrics."""
        avg_tokens = 0.0
        if self.stats.successful_calls > 0:
            avg_tokens = (self.stats.input_tokens + self.stats.output_tokens) / self.stats.successful_calls

        return {
            "provider": self.stats.provider,
            "model": self.stats.model,
            "base_url": self.base_url,
            "total_calls": self.stats.total_calls,
            "successful_calls": self.stats.successful_calls,
            "failed_calls": self.stats.failed_calls,
            "retries": self.stats.retries,
            "input_tokens": self.stats.input_tokens,
            "output_tokens": self.stats.output_tokens,
            "total_tokens": self.stats.input_tokens + self.stats.output_tokens,
            "avg_tokens_per_call": round(avg_tokens, 2),
            "estimated_external_api_cost_usd": 0.0,
            "notes": "Local inference on user hardware; zero external API charges.",
        }
