"""Provider-agnostic AI service with automatic failover."""

import asyncio
import logging
from typing import Optional

from config import settings
from services.providers.base import AIProvider
from services.providers.gemini_provider import GeminiProvider
from services.providers.openai_provider import OpenAIProvider
from services.providers.groq_provider import GroqProvider
from services.providers.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)


class AIService:
    """
    AI service that manages multiple providers with automatic failover.

    Tries providers in the configured priority order. If one fails,
    automatically falls back to the next available provider.
    """

    def __init__(self):
        # Initialize all providers
        self._provider_map: dict[str, AIProvider] = {
            "gemini": GeminiProvider(),
            "openai": OpenAIProvider(),
            "groq": GroqProvider(),
            "anthropic": AnthropicProvider(),
        }

        # Build ordered provider list based on config priority
        self._providers: list[AIProvider] = []
        for name in settings.AI_PROVIDER_PRIORITY:
            name = name.strip().lower()
            if name in self._provider_map:
                provider = self._provider_map[name]
                if provider.is_available():
                    self._providers.append(provider)
                    logger.info(f"AI provider '{name}' is available and registered")
                else:
                    logger.warning(f"AI provider '{name}' is configured but no API key found")

        if not self._providers:
            logger.error(
                "No AI providers available! Please set at least one API key in .env"
            )

    @property
    def available_providers(self) -> list[str]:
        """Return list of available provider names."""
        return [p.name for p in self._providers]

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Generate AI response with automatic failover across providers.

        Args:
            system_prompt: System/role instruction for the AI.
            user_prompt: User message/data to analyze.
            timeout: Timeout in seconds per provider call.

        Returns:
            AI-generated text response.

        Raises:
            RuntimeError: If all providers fail.
        """
        timeout = timeout or settings.AI_CALL_TIMEOUT
        errors: list[str] = []

        for provider in self._providers:
            try:
                logger.info(f"Trying AI provider: {provider.name}")
                response = await asyncio.wait_for(
                    provider.generate(system_prompt, user_prompt),
                    timeout=timeout,
                )
                logger.info(f"Successfully got response from {provider.name}")
                return response

            except asyncio.TimeoutError:
                error_msg = f"{provider.name}: Request timed out after {timeout}s"
                logger.warning(error_msg)
                errors.append(error_msg)

            except Exception as e:
                error_msg = f"{provider.name}: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)

        # All providers failed
        error_summary = "; ".join(errors)
        raise RuntimeError(
            f"All AI providers failed. Errors: {error_summary}"
        )


# Singleton instance
ai_service = AIService()
