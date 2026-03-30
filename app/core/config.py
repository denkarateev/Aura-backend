import os
import json

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:pass@localhost:5433/hookahmix"
)

SECRET_KEY = os.getenv("SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

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
    "secret_lounge_yauza": {"gallery_secret_lounge", "secretloungeyauza"},
    "must_have": {"musthave"},
    "darkside": {"darkside"},
    "hoob": {"hoob"},
    "alpha_hookah": {"alphahookah", "alpha_hookah"},
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
