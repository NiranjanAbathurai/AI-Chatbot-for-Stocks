"""OpenAI GPT AI provider with automatic model fallback.

Maintains a ranked list of OpenAI models (newest first).  When a model is
deprecated or removed, the provider automatically tries the next model in
the list — no redeployment needed.

You can pin a specific model via the OPENAI_MODEL environment variable.
"""

import logging
import os

from openai import AsyncOpenAI

from .base import AIProvider
from config import settings

logger = logging.getLogger(__name__)

# Ordered from newest/best free-tier model to oldest.
# When OpenAI deprecates a model, the next one is tried automatically.
OPENAI_FALLBACK_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
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
    override = os.getenv("OPENAI_MODEL", "").strip()
    models = list(OPENAI_FALLBACK_MODELS)
    if override:
        if override in models:
            models.remove(override)
        models.insert(0, override)
    return models


class OpenAIProvider(AIProvider):
    """OpenAI GPT API provider with automatic model fallback."""

    def __init__(self):
        if self.is_available():
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            self._client = None

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(
            settings.OPENAI_API_KEY
            and settings.OPENAI_API_KEY != "your_openai_key_here"
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._client:
            raise RuntimeError("OpenAI provider is not configured")

        models = _build_model_list()

        for i, model in enumerate(models):
            try:
                logger.info(f"OpenAI: trying model '{model}'")
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
                    logger.info(f"OpenAI: success with model '{model}'")
                    return content
                raise RuntimeError("OpenAI returned empty response")

            except Exception as e:
                if _is_model_not_found(e) and i < len(models) - 1:
                    logger.warning(
                        f"OpenAI: model '{model}' unavailable ({e}) — trying next..."
                    )
                    continue
                logger.error(f"OpenAI API error: {e}")
                raise

        raise RuntimeError("OpenAI: all fallback models exhausted")
