"""
seed_masters.py — Seed 8 masters from MasterCatalog.swift into production DB.

Usage:
    python seed_masters.py

Env vars:
    API_BASE_URL   — default http://188.253.19.166:8000
    ADMIN_EMAIL    — admin account email (must already exist)
    ADMIN_PASSWORD — admin account password
"""
import json
import os
import sys
from urllib import error, request

BASE_URL = os.getenv("API_BASE_URL", "http://188.253.19.166:8000").rstrip("/")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


class APIError(Exception):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"API error {status_code}: {body}")
        self.status_code = status_code
        self.body = body


def api_request(method: str, path: str, payload=None, token: str | None = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}{path}", data=data, headers=headers, method=method
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise APIError(exc.code, body) from exc


# ----- Master seed data (from MasterCatalog.swift) -------------------------

MASTERS = [
    {
        "id": "master_alexey",
        "handle": "alexey_smoke",
        "display_name": "Алексей Дымов",
        "bio": "8 лет за кальяном. Специализация — фруктовые и цитрусовые миксы. Работал в трёх ведущих заведениях Москвы.",
        "current_lounge_id": "hookahplace_mars",
        "mixes_count": 27,
        "followers_count": 1240,
        "rating": 4.9,
        "work_history": [
            {"lounge_id": "secret_yauza", "started_at": "2020-03-01", "ended_at": "2022-09-01"},
            {"lounge_id": "hookahplace_mars", "started_at": "2022-10-01", "ended_at": None},
        ],
    },
    {
        "id": "master_daria",
        "handle": "daria_vapor",
        "display_name": "Дарья Туманова",
        "bio": "Победитель Moscow Hookah Cup 2024. Делаю миксы, которые удивляют с первой затяжки.",
        "current_lounge_id": "secret_yauza",
        "mixes_count": 34,
        "followers_count": 2100,
        "rating": 5.0,
        "work_history": [
            {"lounge_id": "smoky_lab", "started_at": "2021-06-01", "ended_at": "2023-04-01"},
            {"lounge_id": "secret_yauza", "started_at": "2023-05-01", "ended_at": None},
        ],
    },
    {
        "id": "master_roman",
        "handle": "roman_craft",
        "display_name": "Роман Крафтов",
        "bio": "Крафтовый подход к каждому клиенту. Люблю экспериментировать с Must Have и Darkside.",
        "current_lounge_id": "hookahplace_vdnh",
        "mixes_count": 19,
        "followers_count": 870,
        "rating": 4.7,
        "work_history": [
            {"lounge_id": "hookahplace_vdnh", "started_at": "2022-01-01", "ended_at": None},
        ],
    },
    {
        "id": "master_irina",
        "handle": "irina_aroma",
        "display_name": "Ирина Ароматова",
        "bio": "Специалист по ягодным и десертным линейкам. Помогу подобрать идеальный микс под настроение.",
        "current_lounge_id": "ember_studio",
        "mixes_count": 22,
        "followers_count": 1530,
        "rating": 4.8,
        "work_history": [
            {"lounge_id": "mist_bar", "started_at": "2020-11-01", "ended_at": "2022-07-01"},
            {"lounge_id": "ember_studio", "started_at": "2022-08-01", "ended_at": None},
        ],
    },
    {
        "id": "master_dmitry",
        "handle": "dmitry_hookah",
        "display_name": "Дмитрий Кальянов",
        "bio": "Профессиональный кальянщик 6 лет. Специализация — мятные и освежающие композиции.",
        "current_lounge_id": "myata_tulskaya",
        "mixes_count": 41,
        "followers_count": 3200,
        "rating": 4.9,
        "work_history": [
            {"lounge_id": "hookahplace_studio", "started_at": "2019-05-01", "ended_at": "2021-12-01"},
            {"lounge_id": "myata_tulskaya", "started_at": "2022-01-01", "ended_at": None},
        ],
    },
    {
        "id": "master_anna",
        "handle": "anna_smoke",
        "display_name": "Анна Смокова",
        "bio": "Работаю только с проверенными брендами. Каждый микс — это история.",
        "current_lounge_id": "smoky_lab",
        "mixes_count": 15,
        "followers_count": 640,
        "rating": 4.6,
        "work_history": [
            {"lounge_id": "smoky_lab", "started_at": "2021-09-01", "ended_at": None},
        ],
    },
    {
        "id": "master_pavel",
        "handle": "pavel_master",
        "display_name": "Павел Мастеров",
        "bio": "Люблю нестандартные сочетания. Black Burn + Satyr = мой стиль.",
        "current_lounge_id": "mist_bar",
        "mixes_count": 31,
        "followers_count": 1870,
        "rating": 4.8,
        "work_history": [
            {"lounge_id": "hookahplace_urban", "started_at": "2020-03-01", "ended_at": "2023-01-01"},
            {"lounge_id": "mist_bar", "started_at": "2023-02-01", "ended_at": None},
        ],
    },
    {
        "id": "master_ekaterina",
        "handle": "kate_vapor",
        "display_name": "Екатерина Вейп",
        "bio": "Авторские миксы для тех, кто ценит лёгкость и яркость вкуса.",
        "current_lounge_id": "hookahplace_rockstar",
        "mixes_count": 11,
        "followers_count": 490,
        "rating": 4.7,
        "work_history": [
            {"lounge_id": "hookahplace_rockstar", "started_at": "2023-03-01", "ended_at": None},
        ],
    },
]


def get_admin_token() -> str:
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("ERROR: Set ADMIN_EMAIL and ADMIN_PASSWORD env vars")
        sys.exit(1)
    try:
        resp = api_request("POST", "/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        token = resp.get("token")
        if not token:
            print(f"ERROR: No token in login response: {resp}")
            sys.exit(1)
        print(f"  Logged in as admin (user_id={resp.get('user_id')})")
        return token
    except APIError as e:
        print(f"ERROR: Admin login failed: {e}")
        sys.exit(1)


def seed_master(master: dict, token: str):
    master_id = master["id"]

    # Step 1: Create master profile
    try:
        resp = api_request("POST", "/masters", {
            "id": master_id,
            "handle": master["handle"],
            "display_name": master["display_name"],
            "bio": master.get("bio"),
            "current_lounge_id": master.get("current_lounge_id"),
            "mixes_count": master.get("mixes_count", 0),
            "followers_count": master.get("followers_count", 0),
            "rating": master.get("rating", 0.0),
        }, token=token)
        print(f"  Created master: {master_id} ({master['display_name']})")
    except APIError as e:
        if e.status_code == 409:
            print(f"  Skipped (already exists): {master_id}")
        else:
            print(f"  ERROR creating {master_id}: {e}")
            return

    # Step 2: Seed work history
    for entry in master.get("work_history", []):
        if entry.get("ended_at") is None:
            # Only seed the current workplace via the API endpoint
            # (past entries loaded directly via startup seed below)
            continue
    # Use the work-history endpoint for historical entries (all non-current)
    for entry in master.get("work_history", []):
        if entry.get("ended_at") is not None:
            # These are past entries — insert directly via raw endpoint
            # We don't have a PATCH endpoint for historical entries in Phase 1
            # They'll be inserted via the DB seed SQL approach
            pass

    # Use POST /masters/{id}/work-history for the current workplace
    # This also sets current_lounge_id
    current_entries = [e for e in master.get("work_history", []) if e.get("ended_at") is None]
    if current_entries:
        ce = current_entries[0]
        try:
            resp = api_request(
                "POST",
                f"/masters/{master_id}/work-history",
                {"lounge_id": ce["lounge_id"], "started_at": ce["started_at"]},
                token=token,
            )
            print(f"    Set current workplace: {ce['lounge_id']}")
        except APIError as e:
            print(f"    WARN: work-history for {master_id}: {e}")


def main():
    print("=" * 60)
    print("Hooka3 — seed_masters.py")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    token = get_admin_token()

    for master in MASTERS:
        print(f"\n[{master['id']}]")
        seed_master(master, token)

    print("\nDone. Verifying seeded masters...")
    try:
        resp = api_request("GET", "/masters?page_size=10")
        total = resp.get("total", "?")
        print(f"  GET /masters → total={total}")
    except APIError as e:
        print(f"  ERROR verifying: {e}")

    print("\nSeed complete.")


if __name__ == "__main__":
    main()
