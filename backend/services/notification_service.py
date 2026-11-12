"""Notification delivery service: Telegram and browser notifications."""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


async def send_telegram_message(message: str) -> bool:
    """
    Send a message via Telegram bot.

    Args:
        message: Text message to send (supports Markdown).

    Returns:
        True if sent successfully, False otherwise.
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping notification")
        return False

    if settings.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token":
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} — {response.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False


async def send_alert_notification(
    ticker: str,
    stock_name: str,
    trigger: str,
    message: str,
    priority: str = "medium",
) -> bool:
    """
    Send an alert notification via all configured channels.

    Args:
        ticker: Stock ticker symbol.
        stock_name: Human-readable stock name.
        trigger: Alert trigger type.
        message: Alert message.
        priority: Alert priority (high, medium, low).

    Returns:
        True if at least one notification was sent.
    """
    priority_emoji = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🟢",
    }

    emoji = priority_emoji.get(priority, "🟡")

    telegram_msg = (
        f"{emoji} *Stock Alert: {stock_name}* ({ticker})\n\n"
        f"*Trigger:* {trigger}\n"
        f"*Details:* {message}\n"
        f"*Priority:* {priority.upper()}"
    )

    sent = await send_telegram_message(telegram_msg)
    return sent
