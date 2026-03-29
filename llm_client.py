"""Shared LLM client with multi-provider parallel dispatch.

Distributes calls across Groq, Cerebras, and OpenRouter to avoid
single-provider rate limits. Each provider has its own API key and models.
"""

import os
import time

from openai import OpenAI


# === Provider groups (each group = one API with its own rate limit) ===
PROVIDER_GROUPS = []  # list of {"name", "api_key", "base_url", "models": [...]}

_gq_key = os.getenv("GROQ_API_KEY", "")
if _gq_key:
    PROVIDER_GROUPS.append({
        "name": "groq",
        "api_key": _gq_key,
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    })

_cb_key = os.getenv("CEREBRAS_API_KEY", "")
if _cb_key:
    PROVIDER_GROUPS.append({
        "name": "cerebras",
        "api_key": _cb_key,
        "base_url": "https://api.cerebras.ai/v1",
        "models": ["llama-4-scout-17b-16e-instruct", "llama3.3-70b"],
    })

_or_key = os.getenv("OPENROUTER_API_KEY", "")
if _or_key:
    _or_primary = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    _or_models = [
        # All free ($0) models only
        "meta-llama/llama-3.3-70b-instruct:free",
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "google/gemma-3-27b-it:free",
        "openai/gpt-oss-120b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "stepfun/step-3.5-flash:free",
        "minimax/minimax-m2.5:free",
    ]
    ordered = _or_models
    PROVIDER_GROUPS.append({
        "name": "openrouter",
        "api_key": _or_key,
        "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "models": ordered,
    })

# Flatten for total count
PROVIDERS = []
for g in PROVIDER_GROUPS:
    for model in g["models"]:
        PROVIDERS.append({
            "name": f"{g['name']}/{model.split('/')[-1][:30]}",
            "api_key": g["api_key"],
            "base_url": g["base_url"],
            "model": model,
            "group": g["name"],
        })

NUM_GROUPS = len(PROVIDER_GROUPS)


class LLMClient:
    """Multi-provider LLM client with round-robin group dispatch."""

    def __init__(self):
        self._clients = {}
        self._failed = set()
        self._fail_timestamps = {}

    @property
    def current_model(self) -> str:
        if not PROVIDERS:
            return "none"
        return PROVIDERS[0]["name"]

    def _get_client(self, base_url: str, api_key: str) -> OpenAI:
        key = f"{base_url}|{api_key[:8]}"
        if key not in self._clients:
            self._clients[key] = OpenAI(api_key=api_key, base_url=base_url)
        return self._clients[key]

    def _is_failed(self, pname: str) -> bool:
        if pname not in self._failed:
            return False
        if time.time() - self._fail_timestamps.get(pname, 0) > 60:
            self._failed.discard(pname)
            return False
        return True

    def call(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.1,
        max_tokens: int = 800,
        start_group: int = 0,
    ) -> str:
        """Call LLM with fallback. start_group rotates which provider to try first."""
        if not PROVIDERS:
            return "(no response)"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Build provider order: start from start_group, then round-robin other groups
        ordered_providers = []
        for offset in range(NUM_GROUPS):
            group = PROVIDER_GROUPS[(start_group + offset) % NUM_GROUPS]
            for model in group["models"]:
                ordered_providers.append({
                    "name": f"{group['name']}/{model.split('/')[-1][:30]}",
                    "api_key": group["api_key"],
                    "base_url": group["base_url"],
                    "model": model,
                })

        for provider in ordered_providers:
            pname = provider["name"]
            if self._is_failed(pname):
                continue

            client = self._get_client(provider["base_url"], provider["api_key"])

            for attempt in range(2):
                try:
                    response = client.chat.completions.create(
                        model=provider["model"],
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    content = response.choices[0].message.content
                    if content and content.strip():
                        return content.strip()
                    if attempt == 0:
                        time.sleep(1)
                        continue
                except Exception as e:
                    err = str(e).lower()
                    if any(k in err for k in ["429", "quota", "rate limit", "402", "insufficient"]):
                        if attempt == 0:
                            time.sleep(3)
                            continue
                        break
                    else:
                        if attempt == 0:
                            time.sleep(1)
                            continue
                        break

            print(f"[LLM] {pname} failed, trying next...")
            self._failed.add(pname)
            self._fail_timestamps[pname] = time.time()

        return "(no response)"


# Singleton
_client = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
