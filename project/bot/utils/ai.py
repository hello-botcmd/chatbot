import logging
import time
import asyncio
import requests
import config

logger = logging.getLogger(__name__)


def call_openrouter(persona: str, history: list, user_message: str) -> tuple:
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
                except (TypeError, ValueError):
                    pass
                logger.warning("OpenRouter 429 — retry after %ds", retry_after)
                return None, retry_after

            if resp.status_code >= 500:
                last_err = f"HTTP {resp.status_code}"
                logger.warning("OpenRouter %s on attempt %d, retrying...", resp.status_code, attempt + 1)
                time.sleep(2 ** attempt)
                continue

            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            if not text:
                return None, None
            return text, None

        except requests.exceptions.Timeout:
            last_err = "timeout"
            logger.warning("OpenRouter timeout on attempt %d", attempt + 1)
            time.sleep(2)
            continue

        except requests.exceptions.ConnectionError as e:
            last_err = str(e)
            logger.warning("OpenRouter connection error: %s", e)
            time.sleep(3)
            continue

        except requests.exceptions.HTTPError as e:
            logger.error("OpenRouter HTTP error: %s", e)
            return None, None

        except (KeyError, IndexError, ValueError) as e:
            logger.error("OpenRouter parse error: %s", e)
            return None, None

        except Exception as e:
            logger.error("OpenRouter unexpected error: %s", e, exc_info=True)
            return None, None

    logger.error("OpenRouter failed after 3 attempts. Last error: %s", last_err)
    return None, None


# Keep old names as aliases so dashboard.py doesn't break
async def generate_reply(persona: str, history: list, user_message: str) -> tuple:
    return await asyncio.to_thread(call_openrouter, persona, history, user_message)


async def fetch_credits() -> dict:
    return await asyncio.to_thread(fetch_credits_sync)


def fetch_credits_sync() -> dict:
    try:
        resp = requests.get(
            config.OPENROUTER_CREDITS_URL,
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
            timeout=15,
        )
        resp.raise_for_status()
        d     = resp.json().get("data", {})
        limit = d.get("limit")
        used  = d.get("usage", 0.0)
        return {
            "used":      round(used, 4),
            "limit":     round(limit, 4)        if limit is not None else None,
            "remaining": round(limit - used, 4) if limit is not None else None,
        }
    except Exception as e:
        logger.error("Credit fetch error: %s", e)
        return {"error": str(e)[:80]}
