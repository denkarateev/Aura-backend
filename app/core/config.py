import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL env is required")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY env is required")
ALGORITHM = "HS256"
# Legacy constant — kept for any code that imports it directly.
# New code should use app.core.security.ACCESS_TOKEN_EXPIRE_MINUTES (15 min).
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# YooKassa — pack purchases. Secret key must NEVER be logged / returned to client.
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "hooka3://bundle_success")
# Deep link the tip checkout WebView returns to once the guest finishes paying.
YOOKASSA_TIP_RETURN_URL = os.getenv("YOOKASSA_TIP_RETURN_URL", "hooka3://tip_success")

# YooKassa Payouts (Выплаты) — SBP payout of accumulated tips to masters.
# SEPARATE product/gateway from acquiring above: own agreement + own keys.
# Master withdrawals are gated behind these — if either is empty the payout
# endpoints return 503 (feature flag), so deploying without them is safe.
YOOKASSA_PAYOUT_ACCOUNT_ID = os.getenv("YOOKASSA_PAYOUT_ACCOUNT_ID", "")
YOOKASSA_PAYOUT_SECRET_KEY = os.getenv("YOOKASSA_PAYOUT_SECRET_KEY", "")

# Master tips — platform commission (%) withheld from each tip. The master's
# withdrawable balance is credited NET of this. Change via env, no redeploy.
TIP_PLATFORM_COMMISSION_PERCENT = float(os.getenv("TIP_PLATFORM_COMMISSION_PERCENT", "10"))
# Minimum single withdrawal (RUB) — SBP payouts have practical lower bounds.
TIP_MIN_PAYOUT_RUB = int(os.getenv("TIP_MIN_PAYOUT_RUB", "100"))

# CRM AI insights — an LLM that reads the guest base + scoring and writes a
# situational analysis + concrete retention actions ("кого вернуть и что дать").
# OpenAI-compatible Chat Completions: works with OpenAI, OpenRouter, or any
# compatible gateway (incl. Kie.ai if it exposes an OpenAI-compatible URL).
# GATED: empty LLM_API_KEY → the AI endpoint returns 503 (deploy stays safe).
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# 2GIS Catalog API — real-time venue busyness ("congestion").
# Get a demo key at https://platform.2gis.ru (self-service, instant).
DGIS_API_KEY = os.getenv("DGIS_API_KEY", "")

# Telegram bot — busyness polling for brand managers.
# Create bot via @BotFather, paste HTTP API token here.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "hooka3_busyness_bot")
# Polling cadence: every N minutes during these Moscow hours.
BUSYNESS_POLL_INTERVAL_MIN = int(os.getenv("BUSYNESS_POLL_INTERVAL_MIN", "30"))
BUSYNESS_POLL_HOUR_START = int(os.getenv("BUSYNESS_POLL_HOUR_START", "14"))  # 14:00 MSK
BUSYNESS_POLL_HOUR_END = int(os.getenv("BUSYNESS_POLL_HOUR_END", "2"))       # 02:00 MSK next day

# Pack catalog — price / comp / hookah-count — kept in sync with iOS BundleTier.
BUNDLE_TIERS = {
    "five":     {"hookahs": 5,   "price_rub": 5500,  "comp_rub": 1000, "days": 30, "seats": 1, "title": "Пак 5 кальянов"},
    "ten":      {"hookahs": 10,  "price_rub": 10500, "comp_rub": 1000, "days": 30, "seats": 1, "title": "Пак 10 кальянов"},
    "cityPass": {"hookahs": None, "price_rub": 11000, "comp_rub": 1000, "days": 30, "seats": 1, "title": "Безлимит месяц"},
    "group":    {"hookahs": 12,  "price_rub": 14000, "comp_rub": 1000, "days": 30, "seats": 4, "title": "Пак для компании"},
}

REWARD_RULES = {
    "daily_login": {
        "title": "Ежедневный вход",
        "points": 5,
        "rating": 0,
        "daily_limit": 1,
    },
    "mix_created": {
        "title": "Новый микс",
        "points": 20,
        "rating": 5,
        "daily_limit": 3,
    },
    "mix_favorited": {
        "title": "Микс сохранили",
        "points": 4,
        "rating": 3,
        "daily_limit": 30,
    },
    "comment_created": {
        "title": "Комментарий отправлен",
        "points": 3,
        "rating": 0,
        "daily_limit": 10,
    },
    "comment_received": {
        "title": "Новый отзыв на микс",
        "points": 2,
        "rating": 2,
        "daily_limit": 20,
    },
}

RATING_LEVELS = [
    (0, "Новичок"),
    (100, "Миксер"),
    (300, "Блендер"),
    (700, "Мастер чаши"),
    (1500, "Hookah Legend"),
]

MIX_SLOT_RULES = [
    (0, 2),
    (100, 4),
    (300, 6),
    (700, 8),
    (1500, 10),
]

MAX_BOWL_HEAT_ATTEMPTS = 3
BOWL_HEAT_TARGET_SCORE = 75
BOWL_HEAT_DURATION_SECONDS = 20

DEFAULT_ADMIN_EMAILS = {"dorf.foto@yandex.ru"}
DEFAULT_ADMIN_USERNAMES = {"dorfden"}
DEFAULT_UNLIMITED_MIX_EMAILS = {
    "hookahplacemars@hooka3.app",
    "musthave.originals.seed@example.com",
    "neon.lounge.seed@example.com",
}
DEFAULT_UNLIMITED_MIX_USERNAMES = {
    "hookahplacemars",
    "musthave",
    "lounge_neon",
}

DEFAULT_BRAND_MANAGER_USERNAMES = {
    "hookahplace_mars": {"hookahplacemars"},
    "secret_yauza": {"gallery_secret_lounge", "secretloungeyauza"},
    "secret_lounge_yauza": {"gallery_secret_lounge", "secretloungeyauza"},
    "must_have": {"musthave"},
    "darkside": {"darkside"},
    "hoob": {"hoob"},
    "alpha_hookah": {"alphahookah", "alpha_hookah"},
    "neon_dreams_lounge": {"neon_dreams", "lounge_neon", "lounge_neon_mgr"},
    "coal_masters_club": {"coal_master"},
    "berry_mist_gallery": {"berry_mist"},
    "citrus_republic": {"citrus_bar"},
    "satyr_laboratory": {"satyr_lab"},
    "mint_pilot_sky": {"mint_pilot"},
    "graphite_seam_studio": {"graphite_seam"},
    "dessert_room_paradise": {"dessert_room"},
    "smoky_trip_retro": {"smoky_trip"},
    "ice_orchard_cool": {"ice_orchard"},
    "atomic_orchard_exotic": {"atomic_orchard"},
    "honey_velvet_sweet": {"honey_velvet"},
    "steel_tropic_fusion": {"steel_tropic"},
    "cream_barrel_classics": {"cream_barrel"},
    "cherry_code_night": {"cherry_code"},
    "berry_harbor_breeze": {"berry_harbor"},
    "ruby_fizz_lounge": {"ruby_fizz"},
    "lemonade_fresh_bar": {"lemonade_bar"},
    "cran_cunade_night": {"cran_cunade"},
    "garnet_gum_premium": {"garnet_gum"},
    "garden_lounge_korolev": {"garden_lounge_korolev"},
    "myata_platinum": {"myata_platinum"},
}


def load_brand_manager_usernames() -> dict[str, set[str]]:
    raw_value = os.getenv("BRAND_MANAGER_USERNAMES_JSON")
    if not raw_value:
        return {
            brand_id: {username.lower() for username in usernames}
            for brand_id, usernames in DEFAULT_BRAND_MANAGER_USERNAMES.items()
        }

    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return {
            brand_id: {username.lower() for username in usernames}
            for brand_id, usernames in DEFAULT_BRAND_MANAGER_USERNAMES.items()
        }

    normalized: dict[str, set[str]] = {}
    for brand_id, usernames in decoded.items():
        if not isinstance(usernames, list):
            continue
        normalized[str(brand_id)] = {
            str(username).strip().lower()
            for username in usernames
            if str(username).strip()
        }

    return normalized or {
        brand_id: {username.lower() for username in usernames}
        for brand_id, usernames in DEFAULT_BRAND_MANAGER_USERNAMES.items()
    }
