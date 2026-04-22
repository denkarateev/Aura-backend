"""
seed_lounge_assets.py
---------------------
Populates lounge_assets for known brand_ids with Unsplash placeholder images
and structured info (cuisine / atmosphere / signature_mix / vibe).

Usage:
    # against prod
    python3 seed_lounge_assets.py

    # against local
    API_BASE_URL=http://localhost:8001 SEED_MANAGER_PASSWORD=xxx python3 seed_lounge_assets.py

Requires a manager account per brand. Uses DEFAULT_BRAND_MANAGER_USERNAMES
from config, so credentials must match existing seed users.
Manager accounts are pre-created by seed_demo_content.py or exist in prod.
"""

import json
import os
import sys
from urllib import error, request

BASE_URL = os.getenv("API_BASE_URL", "http://188.253.19.166:8000").rstrip("/")
MANAGER_PASSWORD = os.getenv("SEED_MANAGER_PASSWORD", "SeedPass123!")

# Unsplash photo base — verified working photo IDs for hookah / lounge theme
UNSPLASH = "https://images.unsplash.com"


def img(photo_id: str, w: int = 800, h: int = 600) -> str:
    return f"{UNSPLASH}/{photo_id}?w={w}&h={h}&fit=crop&q=80"


# ------------------------------------------------------------------
# Brand definitions
# Each entry maps to a brand_id + manager credentials + asset payload.
# ------------------------------------------------------------------
BRAND_ASSETS = [
    {
        "brand_id": "hookahplace_mars",
        "manager_email": "hookahplacemars@hooka3.app",
        "avatar_url": img("photo-1578662996442-48f60103fc96", 400, 400),
        "cover_url": img("photo-1536663815808-535e2280d2c2", 1200, 675),
        "photos": [
            img("photo-1536663815808-535e2280d2c2", 1200, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1578662996442-48f60103fc96", 800, 800),
        ],
        "info": {
            "cuisine": "Авторские миксы, восточная кухня",
            "atmosphere": "Клубная, уютная, приглушённый свет",
            "signature_mix": "Mars Red — MustHave Pinkman + Darkside Raspberry",
            "vibe": "Вечерний lounge с живой музыкой по выходным",
            "address": "Москва, ул. Марсовая, 1",
            "avg_check_rub": 2500,
            "opens": "14:00",
            "closes": "03:00",
        },
    },
    {
        "brand_id": "secret_lounge_yauza",
        "manager_email": "gallery_secret_lounge@hooka3.app",
        "avatar_url": img("photo-1561579025-a6b77a63de6f", 400, 400),
        "cover_url": img("photo-1485872299712-4b80e6bc0002", 1200, 675),
        "photos": [
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1561579025-a6b77a63de6f", 800, 800),
            img("photo-1536663815808-535e2280d2c2", 1200, 800),
        ],
        "info": {
            "cuisine": "Средиземноморская, авторские коктейли",
            "atmosphere": "Секретный подвальный bar, арт-объекты",
            "signature_mix": "Yauza Secret — Satyr Feijoa + MustHave Lime",
            "vibe": "Для своих: тихий, сфокусированный вечер",
            "address": "Москва, набережная Яузы, 7",
            "avg_check_rub": 3200,
            "opens": "16:00",
            "closes": "02:00",
        },
    },
    {
        "brand_id": "must_have",
        "manager_email": "musthave.originals.seed@example.com",
        "avatar_url": img("photo-1561579025-a6b77a63de6f", 400, 400),
        "cover_url": img("photo-1578662996442-48f60103fc96", 1200, 675),
        "photos": [
            img("photo-1578662996442-48f60103fc96", 1200, 800),
            img("photo-1561579025-a6b77a63de6f", 800, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
        ],
        "info": {
            "cuisine": "Авторский табак, бренд-лаунж",
            "atmosphere": "Официальный brand showroom, минимализм",
            "signature_mix": "MustHave Pinkman 100% — чистый монотабак",
            "vibe": "Дегустации новинок, встречи с blender-командой",
            "address": "Москва, Садовое кольцо",
            "avg_check_rub": 2000,
            "opens": "12:00",
            "closes": "23:00",
        },
    },
    {
        "brand_id": "darkside",
        "manager_email": "darkside@hooka3.app",
        "avatar_url": img("photo-1485872299712-4b80e6bc0002", 400, 400),
        "cover_url": img("photo-1536663815808-535e2280d2c2", 1200, 675),
        "photos": [
            img("photo-1536663815808-535e2280d2c2", 1200, 800),
            img("photo-1485872299712-4b80e6bc0002", 1200, 800),
            img("photo-1578662996442-48f60103fc96", 800, 800),
        ],
        "info": {
            "cuisine": "Dark концепт, бар с коктейлями",
            "atmosphere": "Ночной клубный lounge, дым-машина",
            "signature_mix": "Darkside Bergamonstr + Black Burn Black Cola",
            "vibe": "Интенсивный ночной сеанс для ценителей",
            "address": "Москва, ЦАО",
            "avg_check_rub": 3000,
            "opens": "18:00",
            "closes": "06:00",
        },
    },
    {
        "brand_id": "alpha_hookah",
        "manager_email": "alphahookah@hooka3.app",
        "avatar_url": img("photo-1536663815808-535e2280d2c2", 400, 400),
        "cover_url": img("photo-1561579025-a6b77a63de6f", 1200, 675),
        "photos": [
            img("photo-1561579025-a6b77a63de6f", 1200, 800),
            img("photo-1536663815808-535e2280d2c2", 1200, 800),
            img("photo-1578662996442-48f60103fc96", 800, 800),
        ],
        "info": {
            "cuisine": "Кавказская кухня, авторские миксы",
            "atmosphere": "Просторный hall, живые растения",
            "signature_mix": "Alpha Strike — MustHave Berry Holls + Sebero Strawberry",
            "vibe": "Семейный вечер или дружеская компания",
            "address": "Москва, Новый Арбат",
            "avg_check_rub": 2200,
            "opens": "13:00",
            "closes": "01:00",
        },
    },
]

# ------------------------------------------------------------------
# HTTP helper
# ------------------------------------------------------------------


class APIError(Exception):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"API {status_code}: {body}")
        self.status_code = status_code
        self.body = body


def api(method: str, path: str, payload=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else None
    except error.HTTPError as exc:
        raise APIError(exc.code, exc.read().decode(errors="replace")) from exc


def login_or_skip(email: str) -> str | None:
    """Returns bearer token or None if account doesn't exist / wrong password."""
    try:
        result = api("POST", "/login", {"email": email, "password": MANAGER_PASSWORD})
        return result["token"]
    except APIError as exc:
        if exc.status_code in (400, 401, 404, 422):
            return None
        raise


def seed_assets(brand: dict) -> dict:
    token = login_or_skip(brand["manager_email"])
    if token is None:
        # Try fallback seed password
        return {"brand_id": brand["brand_id"], "status": "skipped — manager account not found"}

    payload = {
        "avatar_url": brand["avatar_url"],
        "cover_url": brand["cover_url"],
        "photos": brand["photos"],
        "info": brand["info"],
    }
    try:
        result = api("PUT", f"/lounges/{brand['brand_id']}/assets", payload, token)
        return {"brand_id": brand["brand_id"], "status": "ok", "avatar_url": result.get("avatar_url")}
    except APIError as exc:
        return {"brand_id": brand["brand_id"], "status": f"error {exc.status_code}", "body": exc.body[:200]}


def verify_get(brand_id: str) -> dict:
    """Quick read-back to confirm data is stored."""
    try:
        result = api("GET", f"/lounges/{brand_id}/assets")
        return {
            "brand_id": brand_id,
            "has_avatar": bool(result.get("avatar_url")),
            "photos_count": len(result.get("photos", [])),
            "info_keys": list(result.get("info", {}).keys()),
        }
    except APIError as exc:
        return {"brand_id": brand_id, "error": exc.status_code}


def main():
    print(f"Seeding lounge assets → {BASE_URL}\n")
    results = []
    for brand in BRAND_ASSETS:
        r = seed_assets(brand)
        results.append(r)
        status = r.get("status", "?")
        print(f"  PUT {brand['brand_id']:30s} → {status}")

    print("\nVerifying (GET /lounges/{id}/assets):\n")
    verifications = []
    for brand in BRAND_ASSETS:
        v = verify_get(brand["brand_id"])
        verifications.append(v)
        if "error" in v:
            print(f"  GET {brand['brand_id']:30s} → ERROR {v['error']}")
        else:
            print(
                f"  GET {brand['brand_id']:30s} → "
                f"avatar={'✓' if v['has_avatar'] else '✗'}  "
                f"photos={v['photos_count']}  "
                f"info_keys={v['info_keys']}"
            )

    summary = {
        "base_url": BASE_URL,
        "brands_processed": len(results),
        "brands_ok": sum(1 for r in results if r.get("status") == "ok"),
        "brands_skipped": sum(1 for r in results if "skipped" in r.get("status", "")),
        "details": results,
        "verification": verifications,
    }
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
