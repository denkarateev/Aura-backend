"""
setup_manager_accounts.py
-------------------------
Creates manager accounts for all brands (via API).
Run before seed_lounge_assets.py.

Usage:
    python3 setup_manager_accounts.py
"""

import json
import os
from urllib import error, request

BASE_URL = os.getenv("API_BASE_URL", "http://188.253.19.166:8000").rstrip("/")
PASSWORD = os.getenv("SEED_MANAGER_PASSWORD", "SeedPass123!")

# Exact emails from seed_lounge_assets.py
MANAGER_EMAILS = {
    "hookahplacemars@hooka3.app",
    "gallery_secret_lounge@hooka3.app",
    "musthave.originals.seed@example.com",
    "darkside@hooka3.app",
    "alphahookah@hooka3.app",
    "lounge_neon@hooka3.app",
    "coal_master@hooka3.app",
    "berry_mist@hooka3.app",
    "citrus_bar@hooka3.app",
    "satyr_lab@hooka3.app",
    "mint_pilot@hooka3.app",
    "graphite_seam@hooka3.app",
    "dessert_room@hooka3.app",
    "smoky_trip@hooka3.app",
    "ice_orchard@hooka3.app",
    "atomic_orchard@hooka3.app",
    "honey_velvet@hooka3.app",
    "steel_tropic@hooka3.app",
    "cream_barrel@hooka3.app",
    "cherry_code@hooka3.app",
    "berry_harbor@hooka3.app",
    "ruby_fizz@hooka3.app",
    "lemonade_bar@hooka3.app",
    "cran_cunade@hooka3.app",
    "garnet_gum@hooka3.app",
}


class APIError(Exception):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"API {status_code}: {body}")
        self.status_code = status_code


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


def ensure_account(email: str, username: str) -> dict:
    """Create account if not exists, else login."""
    # Try login first
    try:
        result = api("POST", "/login", {"email": email, "password": PASSWORD})
        return {"email": email, "username": username, "status": "exists", "user_id": result.get("user_id")}
    except APIError as exc:
        if exc.status_code not in (400, 401, 404):
            raise

    # Create
    try:
        result = api("POST", "/signup", {
            "email": email,
            "password": PASSWORD,
            "username": username,
        })
        return {"email": email, "username": username, "status": "created", "user_id": result.get("user_id")}
    except APIError as exc:
        return {"email": email, "username": username, "status": f"error {exc.status_code}"}


def main():
    print(f"Setting up manager accounts → {BASE_URL}\n")

    results = []
    for email in sorted(MANAGER_EMAILS):
        username = email.split("@")[0]
        r = ensure_account(email, username)
        results.append(r)
        status = r.get("status", "?")
        print(f"  {email:40s} → {status}")

    summary = {
        "base_url": BASE_URL,
        "accounts_total": len(results),
        "created": sum(1 for r in results if r.get("status") == "created"),
        "exists": sum(1 for r in results if r.get("status") == "exists"),
        "errors": sum(1 for r in results if "error" in r.get("status", "")),
    }
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Setup failed: {exc}")
        import traceback
        traceback.print_exc()
