"""Auto-discover available AI models from each provider's API.

Runs on startup and daily at midnight (IST) to keep model lists fresh.
When a provider deprecates a model, the next discovery cycle automatically
picks up the replacement — no manual code changes needed.

Each provider's discovery function queries the provider's model listing API
and returns a ranked list of suitable models (best first).

The discovered models are cached in-memory and used by the provider classes
instead of hardcoded fallback lists.
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

# ── In-memory cache of discovered models ────────────────────────
_model_cache: dict[str, list[str]] = {}
_last_discovery: Optional[datetime] = None


def get_cached_models(provider: str) -> list[str]:
    """Get cached model list for a provider. Returns empty list if not yet discovered."""
    return _model_cache.get(provider, [])


def get_last_discovery_time() -> Optional[datetime]:
    """Get the timestamp of the last successful discovery run."""
    return _last_discovery


# ── Gemini Model Discovery ──────────────────────────────────────

async def discover_gemini_models() -> list[str]:
    """Query Google's Gemini API for available models.

    Uses the models.list endpoint to find all available generative models,
    then ranks them by preference (flash models first, newer versions first).
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_key_here":
        logger.debug("Gemini: no API key — skipping discovery")
        return []

    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            )
            if resp.status_code != 200:
                logger.warning(f"Gemini model discovery failed: HTTP {resp.status_code}")
                return []

            data = resp.json()
            models_data = data.get("models", [])

        # Filter for generateContent-capable models
        suitable = []
        for m in models_data:
            name = m.get("name", "")  # e.g. "models/gemini-2.0-flash"
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                # Strip "models/" prefix
                model_id = name.replace("models/", "")
                suitable.append(model_id)

        if not suitable:
            logger.warning("Gemini: no suitable models found via API")
            return []

        # Rank models: prefer flash variants, newer versions first
        ranked = _rank_gemini_models(suitable)
        logger.info(f"Gemini: discovered {len(ranked)} models: {ranked[:5]}...")
        return ranked

    except Exception as e:
        logger.warning(f"Gemini model discovery error: {e}")
        return []


def _rank_gemini_models(models: list[str]) -> list[str]:
    """Rank Gemini models by preference: flash > pro, newer > older."""

    def _score(model: str) -> tuple:
        m = model.lower()
        # Prefer flash over pro
        is_flash = 1 if "flash" in m else 0
        # Prefer non-lite over lite
        is_lite = 0 if "lite" not in m else 1
        # Prefer non-experimental
        is_exp = 0 if "exp" not in m and "preview" not in m else 1
        # Extract version number for sorting (higher = newer = better)
        version = 0.0
        ver_match = re.search(r"gemini-(\d+\.?\d*)", m)
        if ver_match:
            try:
                version = float(ver_match.group(1))
            except ValueError:
                pass
        # Sort: higher version first, flash first, non-lite first, non-exp first
        return (-version, -is_flash, is_lite, is_exp, model)

    return sorted(models, key=_score)


# ── Groq Model Discovery ───────────────────────────────────────

async def discover_groq_models() -> list[str]:
    """Query Groq's API for available models.

    Uses the /models endpoint to find all available chat models,
    then ranks them by preference (larger models first).
    """
    api_key = settings.GROQ_API_KEY
    if not api_key or api_key == "your_groq_key_here":
        logger.debug("Groq: no API key — skipping discovery")
        return []

    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                logger.warning(f"Groq model discovery failed: HTTP {resp.status_code}")
                return []

            data = resp.json()
            models_data = data.get("data", [])

        # Filter for active, non-whisper, non-embedding models
        suitable = []
        for m in models_data:
            model_id = m.get("id", "")
            # Skip audio/whisper/embedding/guard models
            if any(skip in model_id.lower() for skip in (
                "whisper", "tts", "embed", "guard", "tool-use",
                "distil", "playai",
            )):
                continue
            # Only include models that are likely chat-capable
            if any(kw in model_id.lower() for kw in (
                "llama", "mixtral", "gemma", "qwen", "deepseek",
            )):
                suitable.append(model_id)

        if not suitable:
            logger.warning("Groq: no suitable models found via API")
            return []

        ranked = _rank_groq_models(suitable)
        logger.info(f"Groq: discovered {len(ranked)} models: {ranked[:5]}...")
        return ranked

    except Exception as e:
        logger.warning(f"Groq model discovery error: {e}")
        return []


def _rank_groq_models(models: list[str]) -> list[str]:
    """Rank Groq models by preference: larger > smaller, newer > older."""

    def _score(model: str) -> tuple:
        m = model.lower()
        # Extract parameter count (e.g., 70b, 8b)
        param_count = 0
        param_match = re.search(r"(\d+)b", m)
        if param_match:
            param_count = int(param_match.group(1))
        # Prefer llama over others
        is_llama = 0 if "llama" in m else 1
        # Prefer non-preview
        is_preview = 1 if "preview" in m else 0
        # Prefer versatile variants
        is_versatile = 0 if "versatile" in m else 1
        # Extract version (3.3 > 3.2 > 3.1 > 3)
        version = 0.0
        ver_match = re.search(r"llama-?(\d+\.?\d*)", m)
        if ver_match:
            try:
                version = float(ver_match.group(1))
            except ValueError:
                pass
        # Sort: higher version, larger params, llama first, non-preview
        return (-version, -param_count, is_llama, is_versatile, is_preview, model)

    return sorted(models, key=_score)


# ── OpenAI Model Discovery ─────────────────────────────────────

async def discover_openai_models() -> list[str]:
    """Query OpenAI's API for available models."""
    api_key = settings.OPENAI_API_KEY
    if not api_key or api_key == "your_openai_key_here":
        logger.debug("OpenAI: no API key — skipping discovery")
        return []

    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                logger.warning(f"OpenAI model discovery failed: HTTP {resp.status_code}")
                return []

            data = resp.json()
            models_data = data.get("data", [])

        suitable = []
        for m in models_data:
            model_id = m.get("id", "")
            # Only include GPT chat models
            if model_id.startswith("gpt-") and "instruct" not in model_id:
                suitable.append(model_id)

        if not suitable:
            logger.warning("OpenAI: no suitable models found via API")
            return []

        ranked = _rank_openai_models(suitable)
        logger.info(f"OpenAI: discovered {len(ranked)} models: {ranked[:5]}...")
        return ranked

    except Exception as e:
        logger.warning(f"OpenAI model discovery error: {e}")
        return []


def _rank_openai_models(models: list[str]) -> list[str]:
    """Rank OpenAI models: gpt-4o-mini first (cheapest), then gpt-4o, etc."""

    def _score(model: str) -> tuple:
        m = model.lower()
        # Prefer mini variants (cheapest)
        is_mini = 0 if "mini" in m else 1
        # Prefer 4o over 4-turbo over 3.5
        if "4o" in m:
            gen = 0
        elif "4-turbo" in m or "4-" in m:
            gen = 1
        elif "3.5" in m:
            gen = 2
        else:
            gen = 3
        return (is_mini, gen, model)

    return sorted(models, key=_score)


# ── Main Discovery Runner ──────────────────────────────────────

async def run_model_discovery():
    """Discover available models from all configured providers.

    Called on startup and daily at midnight. Results are cached in-memory
    and used by provider classes instead of hardcoded fallback lists.
    """
    global _model_cache, _last_discovery

    logger.info("[ModelDiscovery] Starting AI model discovery...")
    start = datetime.now()

    # Run all discoveries concurrently
    results = await asyncio.gather(
        discover_gemini_models(),
        discover_groq_models(),
        discover_openai_models(),
        return_exceptions=True,
    )

    provider_names = ["gemini", "groq", "openai"]
    for name, result in zip(provider_names, results):
        if isinstance(result, Exception):
            logger.warning(f"Model discovery failed for {name}: {result}")
        elif result:
            _model_cache[name] = result
            logger.info(f"[ModelDiscovery] {name}: {len(result)} models cached (top: {result[0]})")
        else:
            logger.info(f"[ModelDiscovery] {name}: no models discovered (will use hardcoded fallbacks)")

    _last_discovery = datetime.now()
    elapsed = (datetime.now() - start).total_seconds()
    logger.info(
        f"[ModelDiscovery] Complete in {elapsed:.1f}s - "
        f"cached: {', '.join(f'{k}({len(v)})' for k, v in _model_cache.items())}"
    )
