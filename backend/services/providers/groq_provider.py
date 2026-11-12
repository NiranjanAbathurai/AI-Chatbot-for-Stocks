"""Groq (Llama) AI provider implementation."""

import logging
from groq import AsyncGroq

from .base import AIProvider
from config import settings

logger = logging.getLogger(__name__)


class GroqProvider(AIProvider):
    """Groq API provider (Llama models)."""

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

        try:
            response = await self._client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
            )

            content = response.choices[0].message.content
            if content:
                return content
            raise RuntimeError("Groq returned empty response")

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise
