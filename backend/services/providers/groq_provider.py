"""Groq (Llama) AI provider with automatic model fallback.

Maintains a ranked list of Groq-hosted models (newest first).  When a model
is removed from Groq's free tier, the provider automatically tries the next
model in the list — no redeployment needed.

You can pin a specific model via the GROQ_MODEL environment variable.
"""

import logging
import os

from groq import AsyncGroq

from .base import AIProvider
from config import settings

logger = logging.getLogger(__name__)

# Ordered from newest/best free-tier model to oldest.
# When Groq removes a model, the next one is tried automatically.
GROQ_FALLBACK_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


def _is_model_not_found(err: Exception) -> bool:
    """Check if the error indicates the model doesn't exist / is deprecated."""
    msg = str(err).lower()
    return any(
        kw in msg
        for kw in ("not found", "not exist", "deprecated", "decommissioned", "unavailable", "invalid model")
    ) or getattr(err, "status_code", None) == 404


def _build_model_list() -> list[str]:
    """Build the model list, putting any env-var override first."""
    override = os.getenv("GROQ_MODEL", "").strip()
    models = list(GROQ_FALLBACK_MODELS)
    if override:
        if override in models:
            models.remove(override)
        models.insert(0, override)
    return models


class GroqProvider(AIProvider):
    """Groq API provider with automatic model fallback."""

    def __init__(self):
        if self.is_available():
            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        else:
            self._client = None

    @property
    def name(self) -> str:
        return "groq"

    def is_available(self) -> bool:
        return bool(
            settings.GROQ_API_KEY
            and settings.GROQ_API_KEY != "your_groq_key_here"
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._client:
            raise RuntimeError("Groq provider is not configured")

        models = _build_model_list()

        for i, model in enumerate(models):
            try:
                logger.info(f"Groq: trying model '{model}'")
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=2048,
                )

                content = response.choices[0].message.content
                if content:
                    logger.info(f"Groq: success with model '{model}'")
                    return content
                raise RuntimeError("Groq returned empty response")

            except Exception as e:
                if _is_model_not_found(e) and i < len(models) - 1:
                    logger.warning(
                        f"Groq: model '{model}' unavailable ({e}) — trying next..."
                    )
                    continue
                logger.error(f"Groq API error: {e}")
                raise

        raise RuntimeError("Groq: all fallback models exhausted")
