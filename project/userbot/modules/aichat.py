"""
userbot/modules/aichat.py
─────────────────────────
Handles for each Pyrogram userbot client:
  • AI auto-reply on private DMs
  • Paid-photo trigger on keyword list
  • Per-peer asyncio lock (no double-firing)
  • Persistent typing indicator during AI call
  • Robust error recovery — never silently dies
"""

import asyncio
import logging
import time

from pyrogram import Client, filters
from pyrogram.enums import ChatAction
from pyrogram.errors import (
    FloodWait,
    MessageNotModified,
    PeerIdInvalid,
    UserIsBlocked,
)
from pyrogram.types import Message

import config
from bot.utils import db
from bot.utils.ai import call_openrouter
from bot.utils.helpers import trim_history

logger = logging.getLogger(__name__)

_locks: dict[str, dict[str, asyncio.Lock]] = {}


def _get_lock(sid: str, peer: str) -> asyncio.Lock:
    if sid not in _locks:
        _locks[sid] = {}
    if peer not in _locks[sid]:
        _locks[sid][peer] = asyncio.Lock()
    return _locks[sid][peer]


async def _typing_loop(client: Client, chat_id: int, stop: asyncio.Event):
    while not stop.is_set():
        try:
            await client.send_chat_action(chat_id, ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4)
        except asyncio.TimeoutError:
            pass


def register(app: Client, session_id: str) -> None:

    @app.on_message(
        filters.private
        & ~filters.me
        & ~filters.bot
        & ~filters.service
    )
    async def on_private_dm(client: Client, message: Message):
        try:
            await _handle_dm(client, message, session_id)
        except Exception as e:
            logger.error("[%s] Unhandled error in DM handler: %s", session_id, e, exc_info=True)

    logger.info("[%s] aichat handlers registered.", session_id)


async def _handle_dm(client: Client, message: Message, session_id: str):
    msg_text = (message.text or message.caption or "").strip()
    if not msg_text:
        return

    sender = message.from_user
    if not sender:
        return
    peer_id = str(sender.id)

    lock = _get_lock(session_id, peer_id)
    if lock.locked():
        return

    async with lock:
        acc = db.get_account(session_id, config.DEFAULT_PERSONA)
        if acc is None:
            logger.warning("[%s] Account not found in DB, skipping.", session_id)
            return

        store = db.load()

        global_on  = store.get("global_ai_on", False)
        account_on = acc.get("ai_enabled", False)
        if not global_on and not account_on:
            return

        now = time.time()

        # ── PAID PHOTO TRIGGER (multi-word) ───────────────────────────────────
        trigger_words = list(getattr(config, "PAID_TRIGGER_WORDS", []))
        # backwards compat with old single-word key
        single = getattr(config, "PAID_TRIGGER_WORD", "")
        if single and single not in trigger_words:
            trigger_words.append(single)

        msg_lower = msg_text.lower()
        triggered = any(
            word.strip().lower() in msg_lower
            for word in trigger_words
            if word.strip()
        )
        if triggered:
            await _send_paid_photo(client, message, acc, session_id, peer_id)
            return

        # ── rate-limit gate ───────────────────────────────────────────────────
        rate_until = acc.get("rate_limited_until", 0)
        if now < rate_until:
            logger.info("[%s] Rate limited for %ds more, skipping.", session_id, int(rate_until - now))
            return

        # ── per-peer cooldown ─────────────────────────────────────────────────
        last_times: dict = acc.get("last_msg_time", {})
        if now - last_times.get(peer_id, 0.0) < config.COOLDOWN_SECONDS:
            return

        last_times[peer_id] = now
        db.update_account(session_id, last_msg_time=last_times)

        if len(msg_text) > 1000:
            msg_text = msg_text[:1000]

        # ── typing indicator ──────────────────────────────────────────────────
        stop_typing = asyncio.Event()
        typing_task = asyncio.create_task(
            _typing_loop(client, message.chat.id, stop_typing)
        )

        reply_text  = None
        retry_after = None
        try:
            history = acc.get("history", {}).get(peer_id, [])
            reply_text, retry_after = await asyncio.to_thread(
                call_openrouter,
                acc["persona"],
                history,
                msg_text,
            )
        except Exception as e:
            logger.error("[%s] AI call exception: %s", session_id, e, exc_info=True)
        finally:
            stop_typing.set()
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

        if retry_after:
            db.update_account(session_id, rate_limited_until=time.time() + retry_after)
            logger.warning("[%s] Rate limited, cooldown set for %ds.", session_id, retry_after)
            return

        if not reply_text:
            logger.warning("[%s] Empty reply from AI, skipping.", session_id)
            return

        sent = await _safe_reply(client, message, reply_text, session_id)
        if not sent:
            return

        db.increment_api_calls()

        history = acc.get("history", {}).get(peer_id, [])
        history.append({"role": "user",      "text": msg_text})
        history.append({"role": "assistant", "text": reply_text})
        history = trim_history(history, config.MAX_HISTORY_TURNS)

        full_history = acc.get("history", {})
        full_history[peer_id] = history
        db.update_account(session_id, history=full_history)


async def _send_paid_photo(
    client: Client,
    message: Message,
    acc: dict,
    session_id: str,
    peer_id: str,
):
    """
    Send paid photo from local file path (preferred) or file_id fallback.
    Local path avoids cross-DC file_id issues between bot and userbot.
    """
    from pathlib import Path

    photo_path = acc.get("paid_photo_path")
    photo_id   = acc.get("paid_photo_file_id")

    if not photo_path and not photo_id:
        logger.info("[%s] Trigger word received but no paid photo set.", session_id)
        return

    stars   = acc.get("paid_stars", 0)
    caption = f"⭐ {stars} Stars" if stars else "📸 Here you go!"

    # prefer local file — always reliable
    send_arg = photo_path if (photo_path and Path(photo_path).exists()) else photo_id

    for attempt in range(3):
        try:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=send_arg,
                caption=caption,
            )
            logger.info("[%s] Paid photo sent to peer %s.", session_id, peer_id)
            return
        except FloodWait as e:
            logger.warning("[%s] FloodWait %ds on paid photo.", session_id, e.value)
            await asyncio.sleep(e.value + 1)
        except (UserIsBlocked, PeerIdInvalid) as e:
            logger.warning("[%s] Cannot send paid photo: %s", session_id, e)
            return
        except Exception as e:
            logger.error("[%s] Paid photo error (attempt %d): %s", session_id, attempt + 1, e, exc_info=True)
            await asyncio.sleep(2)

    logger.error("[%s] Paid photo failed after 3 attempts.", session_id)


async def _safe_reply(
    client: Client,
    message: Message,
    text: str,
    session_id: str,
) -> bool:
    for attempt in range(3):
        try:
            await message.reply_text(text)
            return True
        except FloodWait as e:
            logger.warning("[%s] FloodWait %ds on reply.", session_id, e.value)
            await asyncio.sleep(e.value + 1)
        except (UserIsBlocked, PeerIdInvalid) as e:
            logger.warning("[%s] Cannot reply: %s", session_id, e)
            return False
        except MessageNotModified:
            return True
        except Exception as e:
            logger.error("[%s] Reply error (attempt %d): %s", session_id, attempt + 1, e, exc_info=True)
            await asyncio.sleep(2)
    return False
