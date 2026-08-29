"""
bot/utils/ai.py
───────────────
Synchronous OpenRouter wrapper.
Always call via asyncio.to_thread() from async code.
"""

import logging
import time

import requests

import config

logger = logging.getLogger(__name__)


def call_openrouter(
    persona: str,
    history: list,
    user_message: str,
) -> tuple:
    """
    Returns:
      (reply_text, None)          — success
      (None,       retry_seconds) — rate limited (caller stays silent)
      (None,       None)          — error (caller stays silent)
    """
    if not config.OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is not set in config.py")
        return None, None

    messages = [{"role": "system", "content": persona}]
    for turn in history:
        role = "assistant" if turn.get("role") in ("model", "assistant") else "user"
        messages.append({"role": role, "content": turn["text"]})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model":       config.OPENROUTER_MODEL,
        "messages":    messages,
        "max_tokens":  200,
        "temperature": 0.9,
    }
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://github.com/your-repo",
        "X-Title":       "TelegramUserbot",
    }

    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(
                config.OPENROUTER_URL,
                json=payload,
                headers=headers,
                timeout=45,
            )

            if resp.status_code == 429:
                retry_after = 60
                try:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                
