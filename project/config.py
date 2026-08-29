# ============================================================
#                    C O N F I G . P Y
#   Edit this file to customise your bot without touching code
# ============================================================

# ── Telegram Bot (Admin Dashboard) ──────────────────────────
BOT_TOKEN = "8607223226:AAFDLuUGKeofa8pTV9qiSPPqDhz1nCVUngI"

# ── Admin user-ids (int) — only these users can use the bot ─
ADMIN_IDS = [8580367479]

# ── Dashboard image URL ─────────────────────────────────────
DASHBOARD_IMAGE_URL = "https://i.ibb.co/nhQQLxK/894e3a6da2af.jpg"

# ── Contact / Support handle ────────────────────────────────
CONTACT_USERNAME = "@sexyiwowu"             # shown on Contact button

# ── Telethon API credentials (get from https://my.telegram.org) ─
TELEGRAM_API_ID   = 36134104                    # replace with your API ID (integer)
TELEGRAM_API_HASH = "7e85000983efb86b5d4739b6680016b2"    # replace with your API Hash (string)

# ── OpenRouter AI ───────────────────────────────────────────
OPENROUTER_API_KEY  = "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"
OPENROUTER_MODEL    = "openai/gpt-4o"       # valid OpenRouter model slug
OPENROUTER_URL      = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/auth/key"

# ── AI Persona (shared default; each account can override) ──
DEFAULT_PERSONA = (
    "You are a friendly assistant. Reply in Hinglish (Hindi + English mix) "
    "in short, natural messages like a close friend would."
)

# ── Userbot behaviour ───────────────────────────────────────
MAX_HISTORY_TURNS   = 6     # conversation turns remembered per user
COOLDOWN_SECONDS    = 5     # minimum seconds between AI replies (per user)

# ── Paid-photo trigger word ─────────────────────────────────
PAID_TRIGGER_WORD   = "send"   # if other person sends this word, bot replies with paid photo
