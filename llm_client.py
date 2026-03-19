"""Shared OpenRouter LLM client with automatic free model fallback.

If the primary model hits rate limits or quota, automatically tries
the next free model. All models are free ($0) on OpenRouter.
"""

import os
import time

from openai import OpenAI


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Models ranked by capability (paid pennies, free as fallback)
MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",       # $0.10/M input — best quality
    "nvidia/nemotron-3-nano-30b-a3b",           # $0.05/M input — fast fallback
    "nvidia/nemotron-3-super-120b-a12b:free",   # Free tier (may have quota limits)
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "stepfun/step-3.5-flash:free",
    "minimax/minimax-m2.5:free",
]

# Allow env override for primary model
PRIMARY_MODEL = os.getenv("OPENROUTER_MODEL", MODELS[0])


class LLMClient:
    """OpenRouter client with automatic model fallback on rate limit / quota exhaustion."""

    def __init__(self):
        self.client = OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        # Build model priority: env primary first, then fallbacks
        self.models = [PRIMARY_MODEL]
        for m in MODELS:
            if m not in self.models:
                self.models.append(m)

        self._current_model_idx = 0
        self._failed_models = set()

    @property
    def current_model(self) -> str:
        return self.models[self._current_model_idx]

    def call(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str:
        """Call LLM with automatic fallback across free models.

        Returns response text, or "(no response)" if all models fail.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Try each model in priority order
        tried = 0

        while tried < len(self.models):
            model = self.models[self._current_model_idx]

            if model in self._failed_models:
                self._advance_model()
                tried += 1
                continue

            success = False
            for attempt in range(2):
                try:
                    response = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    content = response.choices[0].message.content
                    if content and content.strip():
                        return content.strip()
                    # Empty response — retry once, then switch model
                    if attempt == 0:
                        time.sleep(2)
                        continue
                except Exception as e:
                    err = str(e)
                    if any(k in err.lower() for k in ["429", "quota", "rate limit", "402", "insufficient"]):
                        if attempt == 0:
                            time.sleep(5)
                            continue
                        break  # Switch model
                    else:
                        if attempt == 0:
                            time.sleep(2)
                            continue
                        break

            # Model failed after retries — mark and switch
            print(f"[LLM] {model} failed, trying next model...")
            self._failed_models.add(model)
            self._advance_model()
            tried += 1

        return "(no response)"

    def _advance_model(self):
        """Move to next model in priority list."""
        self._current_model_idx = (self._current_model_idx + 1) % len(self.models)


# Singleton instance
_client = None


def get_client() -> LLMClient:
    """Get shared LLM client instance."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
