"""Anthropic Claude AI provider with automatic model fallback.

Maintains a ranked list of Claude models (newest first).  When a model is
deprecated or removed, the provider automatically tries the next model in
the list — no redeployment needed.

Supports both direct Anthropic API and corporate API gateways.  The SDK
auto-detects ANTHROPIC_BASE_URL and ANTHROPIC_API_KEY from system
environment variables.  If a corporate gateway is detected, the provider
uses gateway-compatible model names automatically.

You can pin a specific model via the ANTHROPIC_MODEL environment variable.
"""

import logging
import os

from anthropic import AsyncAnthropic

from .base import AIProvider
from config import settings

logger = logging.getLogger(__name__)

# Model lists for the corporate AbbVie gateway (iliad-emerging-api).
# These use simplified names without date suffixes.
GATEWAY_FALLBACK_MODELS = [
    "claude-4.5-sonnet",
    "claude-4.5-haiku",
    "claude-4.6-sonnet",
    "claude-5-sonnet",
]

# Model lists for direct Anthropic API access.
# Standard Anthropic model names with date suffixes.
DIRECT_FALLBACK_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-haiku-4-20250414",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]


def _is_gateway() -> bool:
    """Check if the SDK is configured to use a corporate API gateway."""
    base_url = os.getenv("ANTHROPIC_BASE_URL", "")
    return bool(base_url and "anthropic.com" not in base_url)


def _is_model_not_found(err: Exception) -> bool:
    """Check if the error indicates the model doesn't exist / is deprecated."""
    msg = str(err).lower()
    return any(
        kw in msg
        for kw in (
            "not found", "not exist", "deprecated", "decommissioned",
            "unavailable", "invalid model", "invalid_request_error",
        )
    ) or getattr(err, "status_code", None) in (400, 404)


def _build_model_list() -> list[str]:
    """Build the model list, putting any env-var override first."""
    override = os.getenv("ANTHROPIC_MODEL", "").strip()
    base_models = GATEWAY_FALLBACK_MODELS if _is_gateway() else DIRECT_FALLBACK_MODELS
    models = list(base_models)
    if override:
        if override in models:
            models.remove(override)
        models.insert(0, override)
    return models


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider with automatic model fallback.

    Supports both direct Anthropic API and corporate gateways.
    The SDK auto-detects ANTHROPIC_BASE_URL and ANTHROPIC_API_KEY
    from system environment variables, so no explicit configuration
    is needed when those are set.
    """

    def __init__(self):
        if self.is_available():
            # Let the SDK auto-detect base_url and api_key from env vars.
            # If ANTHROPIC_BASE_URL is set (corporate gateway), the SDK uses it.
            # If ANTHROPIC_API_KEY is set in env, it takes precedence over .env.
            self._client = AsyncAnthropic()
            base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
            logger.info(f"Anthropic: using base URL '{base_url}'")
            if _is_gateway():
                logger.info("Anthropic: corporate gateway detected — using gateway model names")
        else:
            self._client = None

    @property
    def name(self) -> str:
        return "anthropic"

    def is_available(self) -> bool:
        # Check both .env config and system environment variables
        env_key = os.getenv("ANTHROPIC_API_KEY", "")
        config_key = settings.ANTHROPIC_API_KEY
        has_key = bool(
            (config_key and config_key != "your_anthropic_key_here")
            or (env_key and env_key != "your_anthropic_key_here")
        )
        return has_key

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._client:
            raise RuntimeError("Anthropic provider is not configured")

        models = _build_model_list()

        for i, model in enumerate(models):
            try:
                logger.info(f"Anthropic: trying model '{model}'")
                response = await self._client.messages.create(
                    model=model,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt},
                    ],
                )

                # Extract text from the response content blocks
                content = ""
                for block in response.content:
                    if block.type == "text":
                        content += block.text

                if content:
                    logger.info(f"Anthropic: success with model '{model}'")
                    return content
                raise RuntimeError("Anthropic returned empty response")

            except Exception as e:
                if _is_model_not_found(e) and i < len(models) - 1:
                    logger.warning(
                        f"Anthropic: model '{model}' unavailable ({e}) — trying next..."
                    )
                    continue
                logger.error(f"Anthropic API error: {e}")
                raise

        raise RuntimeError("Anthropic: all fallback models exhausted")
