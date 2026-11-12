"""OpenAI GPT AI provider implementation."""

import logging
from openai import AsyncOpenAI

from .base import AIProvider
from config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """OpenAI GPT API provider."""

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

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
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
            raise RuntimeError("OpenAI returned empty response")

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
