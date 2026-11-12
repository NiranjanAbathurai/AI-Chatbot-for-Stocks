"""Google Gemini AI provider with automatic model fallback.

Maintains a ranked list of Gemini models (newest first).  When a model is
deprecated or removed by Google, the provider automatically tries the next
model in the list — no redeployment needed.

You can pin a specific model via the GEMINI_MODEL environment variable.
"""

import logging
import os

from google import genai
from google.genai import types

from .base import AIProvider
from config import settings

logger = logging.getLogger(__name__)

# Ordered from newest/best free-tier model to oldest.
# When Google deprecates a model, the next one is tried automatically.
# Updated Nov 2026 — older preview models removed.
GEMINI_FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


def _is_model_not_found(err: Exception) -> bool:
    """Check if the error indicates the model doesn't exist / is deprecated."""
    msg = str(err).lower()
    return any(
        kw in msg
        for kw in ("not found", "not exist", "deprecated", "decommissioned", "unavailable", "invalid model")
    )


def _build_model_list() -> list[str]:
    """Build the model list, putting any env-var override first."""
    override = os.getenv("GEMINI_MODEL", "").strip()
    models = list(GEMINI_FALLBACK_MODELS)
    if override:
        if override in models:
            models.remove(override)
        models.insert(0, override)
    return models


class GeminiProvider(AIProvider):
    """Google Gemini API provider with automatic model fallback."""

    def __init__(self):
        if self.is_available():
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        else:
            self._client = None

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(
            settings.GEMINI_API_KEY
            and settings.GEMINI_API_KEY != "your_gemini_key_here"
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._client:
            raise RuntimeError("Gemini provider is not configured")

        models = _build_model_list()

        for i, model in enumerate(models):
            try:
                logger.info(f"Gemini: trying model '{model}'")
                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.7,
                        max_output_tokens=2048,
                    ),
                )

                if response and response.text:
                    logger.info(f"Gemini: success with model '{model}'")
                    return response.text
                raise RuntimeError("Gemini returned empty response")

            except Exception as e:
                if _is_model_not_found(e) and i < len(models) - 1:
                    logger.warning(
                        f"Gemini: model '{model}' unavailable ({e}) — trying next..."
                    )
                    continue
                logger.error(f"Gemini API error: {e}")
                raise

        raise RuntimeError("Gemini: all fallback models exhausted")
