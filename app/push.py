"""APNs HTTP/2 push wrapper.

Authentication: Apple PushKit auth via JWT signed with the Team's APNs
auth key (.p8 ES256). One key works for all our apps + sandbox/production.

Env vars (loaded once on import):
- APNS_KEY_PATH       — path to .p8 file (e.g. /root/apns_auth.p8)
- APNS_KEY_ID         — 10-char key id (filename suffix)
- APNS_TEAM_ID        — 10-char Apple Developer team id
- APNS_BUNDLE_ID      — iOS app bundle id (e.g. com.dorffoto.huka)
- APNS_PRODUCTION     — "true" → production gateway, otherwise sandbox

Token caching: JWT is valid 60 minutes (Apple's hard limit). We refresh
every 50 minutes proactively so a request never sees an expired token.

Usage:
    from app.push import send_push
    send_push(device_token="...", title="Новый микс", body="...")
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional

import httpx
import jwt as pyjwt

logger = logging.getLogger(__name__)

APNS_KEY_PATH = os.environ.get("APNS_KEY_PATH", "/root/apns_auth.p8")
APNS_KEY_ID = os.environ.get("APNS_KEY_ID", "")
APNS_TEAM_ID = os.environ.get("APNS_TEAM_ID", "")
APNS_BUNDLE_ID = os.environ.get("APNS_BUNDLE_ID", "")
APNS_PRODUCTION = os.environ.get("APNS_PRODUCTION", "false").lower() in ("1", "true", "yes")

APNS_HOST = (
    "https://api.push.apple.com"
    if APNS_PRODUCTION
    else "https://api.sandbox.push.apple.com"
)

_jwt_cache = {"token": None, "issued_at": 0}


def _is_configured() -> bool:
    return bool(APNS_KEY_ID and APNS_TEAM_ID and APNS_BUNDLE_ID and Path(APNS_KEY_PATH).exists())


def _load_private_key() -> Optional[str]:
    try:
        return Path(APNS_KEY_PATH).read_text()
    except Exception as e:
        logger.error("APNs key not readable at %s: %s", APNS_KEY_PATH, e)
        return None


def _get_jwt() -> Optional[str]:
    """Returns a valid (cached or freshly minted) APNs provider JWT."""
    now = int(time.time())
    if _jwt_cache["token"] and (now - _jwt_cache["issued_at"]) < 50 * 60:
        return _jwt_cache["token"]
    key = _load_private_key()
    if not key:
        return None
    try:
        token = pyjwt.encode(
            payload={"iss": APNS_TEAM_ID, "iat": now},
            key=key,
            algorithm="ES256",
            headers={"alg": "ES256", "kid": APNS_KEY_ID},
        )
        if isinstance(token, bytes):
            token = token.decode()
        _jwt_cache["token"] = token
        _jwt_cache["issued_at"] = now
        return token
    except Exception as e:
        logger.error("APNs JWT mint failed: %s", e)
        return None


def send_push(
    device_token: str,
    title: str,
    body: str,
    *,
    badge: Optional[int] = None,
    sound: str = "default",
    category: Optional[str] = None,
    payload: Optional[dict] = None,
    priority: int = 10,
    apns_topic: Optional[str] = None,
) -> bool:
    """Single-device APNs push via HTTP/2.

    Returns True on success (apns-id received), False otherwise. Never raises —
    logs and returns False so caller's logic (e.g. fan-out across followers)
    keeps going on a single failure.
    """
    if not _is_configured():
        logger.warning("APNs not configured; skipping push to %s", device_token[:12])
        return False
    token = _get_jwt()
    if not token:
        return False

    aps_body = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": sound,
        }
    }
    if badge is not None:
        aps_body["aps"]["badge"] = badge
    if category:
        aps_body["aps"]["category"] = category
    if payload:
        # Custom keys go alongside the "aps" key, not inside.
        aps_body.update(payload)

    headers = {
        "authorization": f"bearer {token}",
        "apns-topic": apns_topic or APNS_BUNDLE_ID,
        "apns-priority": str(priority),
        "apns-push-type": "alert",
    }

    url = f"{APNS_HOST}/3/device/{device_token}"

    try:
        with httpx.Client(http2=True, timeout=10.0) as client:
            resp = client.post(url, headers=headers, content=json.dumps(aps_body))
        if resp.status_code == 200:
            return True
        logger.warning(
            "APNs %s for %s: %s",
            resp.status_code, device_token[:12], resp.text[:200],
        )
        return False
    except Exception as e:
        logger.error("APNs request failed: %s", e)
        return False


def send_push_to_user(db, user_id: int, title: str, body: str, **kwargs) -> int:
    """Fanout: looks up all device_tokens for `user_id` and sends to each.

    Returns count of successful deliveries. Cleans up token rows that APNs
    explicitly rejects with 410 Unregistered (TODO when we wire response).
    """
    from app.models import DeviceToken  # local import to avoid cycle on cold start
    sent = 0
    rows = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    for row in rows:
        if send_push(row.token, title, body, **kwargs):
            sent += 1
    return sent
