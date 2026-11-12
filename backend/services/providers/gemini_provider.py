"""Google Gemini AI provider implementation using the new google-genai SDK."""

import logging

from google import genai
from google.genai import types

from .base import AIProvider
from config import settings

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Google Gemini API provider using the new google-genai SDK."""

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

        try:
            response = await self._client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )

            if response and response.text:
                return response.text
            raise RuntimeError("Gemini returned empty response")

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
