"""Provider-agnostic AI service with automatic failover.

Features:
- Ordered provider failover based on AI_PROVIDER_PRIORITY
- Configurable per-call timeout (default: AI_CALL_TIMEOUT from config)
- Automatic retry with extended timeout for providers that time out
- Detection and fast-skip of Zscaler/firewall-blocked providers
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from config import settings
from services.providers.base import AIProvider
from services.providers.gemini_provider import GeminiProvider
from services.providers.openai_provider import OpenAIProvider
from services.providers.groq_provider import GroqProvider
from services.providers.anthropic_provider import AnthropicProvider

logger = logging.getLogger(__name__)

# Providers that returned a firewall/proxy block page are cached here
# so we don't waste time retrying them within the same process lifetime.
# Maps provider name -> timestamp of when it was blocked.
_blocked_providers: dict[str, float] = {}
_BLOCK_CACHE_TTL = 300  # Re-check blocked providers after 5 minutes


def _is_firewall_block(error_msg: str) -> bool:
    """Detect if an error response is a corporate firewall/proxy block page."""
    indicators = [
        "zscaler",
        "page blocked",
        "internet security",
        "you don't have permission",
        "not allowed the use of",
        "<!doctype html",
    ]
    lower = error_msg.lower()
    return any(ind in lower for ind in indicators)


@dataclass
class AIResult:
    """Result from an AI generation call, including provider metadata."""
    text: str
    provider: str  # Name of the provider that succeeded (or "none")
    providers_attempted: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)  # provider -> error message
    success: bool = True


class AIService:
    """
    AI service that manages multiple providers with automatic failover.

    Tries providers in the configured priority order. If one fails,
    automatically falls back to the next available provider.

    Resilience features:
    - Retries timed-out providers once with 1.5× timeout (if AI_RETRY_ON_TIMEOUT is enabled)
    - Caches firewall-blocked providers to skip them quickly on subsequent calls
    """

    def __init__(self):
        # Initialize all providers
        self._provider_map: dict[str, AIProvider] = {
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
            "openai": OpenAIProvider(),
            "groq": GroqProvider(),
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

    def _is_provider_blocked(self, name: str) -> bool:
        """Check if a provider is in the firewall-blocked cache."""
        if name not in _blocked_providers:
            return False
        blocked_at = _blocked_providers[name]
        if time.time() - blocked_at > _BLOCK_CACHE_TTL:
            # TTL expired — give it another chance
            del _blocked_providers[name]
            logger.info(f"Provider '{name}' block cache expired — will retry")
            return False
        return True

    async def _try_provider(
        self,
        provider: AIProvider,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
    ) -> str:
        """Attempt a single provider call with timeout. Raises on failure."""
        return await asyncio.wait_for(
            provider.generate(system_prompt, user_prompt),
            timeout=timeout,
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        timeout: Optional[int] = None,
    ) -> AIResult:
        """
        Generate AI response with automatic failover across providers.

        Args:
            system_prompt: System/role instruction for the AI.
            user_prompt: User message/data to analyze.
            timeout: Timeout in seconds per provider call.

        Returns:
            AIResult with the response text, provider used, and attempt metadata.

        Raises:
            RuntimeError: If all providers fail (includes attempt metadata in the exception).
        """
        timeout = timeout or settings.AI_CALL_TIMEOUT
        errors: dict[str, str] = {}
        providers_attempted: list[str] = []
        retry_candidates: list[AIProvider] = []  # Providers that timed out (may succeed with more time)

        for provider in self._providers:
            # Skip providers known to be firewall-blocked
            if self._is_provider_blocked(provider.name):
                logger.info(f"Skipping '{provider.name}' — firewall-blocked (cached)")
                providers_attempted.append(provider.name)
                errors[provider.name] = "Skipped — firewall-blocked (cached)"
                continue

            providers_attempted.append(provider.name)
            try:
                logger.info(f"Trying AI provider: {provider.name} (timeout={timeout}s)")
                response = await self._try_provider(
                    provider, system_prompt, user_prompt, timeout
                )
                logger.info(f"Successfully got response from {provider.name}")
                return AIResult(
                    text=response,
                    provider=provider.name,
                    providers_attempted=providers_attempted,
                    errors=errors,
                    success=True,
                )

            except asyncio.TimeoutError:
                error_msg = f"Request timed out after {timeout}s"
                logger.warning(f"{provider.name}: {error_msg}")
                errors[provider.name] = error_msg
                # Mark as retry candidate — timeout might succeed with more time
                retry_candidates.append(provider)

            except Exception as e:
                error_msg = str(e)[:200]
                logger.warning(f"{provider.name}: {error_msg}")
                errors[provider.name] = error_msg
                # Cache firewall-blocked providers
                if _is_firewall_block(str(e)):
                    _blocked_providers[provider.name] = time.time()
                    logger.warning(
                        f"Provider '{provider.name}' appears firewall-blocked — caching for {_BLOCK_CACHE_TTL}s"
                    )

        # ── Retry phase: try timed-out providers with extended timeout ──
        if retry_candidates and settings.AI_RETRY_ON_TIMEOUT:
            extended_timeout = int(timeout * 1.5)
            logger.info(
                f"Retrying {len(retry_candidates)} timed-out provider(s) with extended timeout ({extended_timeout}s)..."
            )
            for provider in retry_candidates:
                try:
                    logger.info(f"Retry: {provider.name} (timeout={extended_timeout}s)")
                    response = await self._try_provider(
                        provider, system_prompt, user_prompt, extended_timeout
                    )
                    logger.info(f"Retry succeeded for {provider.name}")
                    errors[provider.name] = errors.get(provider.name, "") + " → retry succeeded"
                    return AIResult(
                        text=response,
                        provider=provider.name,
                        providers_attempted=providers_attempted,
                        errors=errors,
                        success=True,
                    )
                except asyncio.TimeoutError:
                    error_msg = f"Retry also timed out after {extended_timeout}s"
                    logger.warning(f"{provider.name}: {error_msg}")
                    errors[provider.name] = error_msg
                except Exception as e:
                    error_msg = f"Retry failed: {str(e)[:150]}"
                    logger.warning(f"{provider.name}: {error_msg}")
                    errors[provider.name] = error_msg

        # All providers failed
        error_summary = "; ".join(f"{k}: {v}" for k, v in errors.items())
        raise RuntimeError(
            f"All AI providers failed. Errors: {error_summary}"
        )


# Singleton instance
ai_service = AIService()
