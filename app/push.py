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

Async design:
- A single httpx.AsyncClient (HTTP/2) is reused across all pushes — one
  TCP/TLS connection to APNs, multiplexed via HTTP/2 streams.
- send_push_async()          — single device, async
- send_push()                — sync wrapper (asyncio.run) for legacy callers
- send_push_to_user_async()  — fan-out to all tokens of one user, async
- send_push_to_user()        — sync wrapper for per-user fan-out
- send_push_fanout_async()   — fan-out to a list of user_ids via gather, async

Usage:
    from app.push import send_push, send_push_to_user, send_push_fanout_async
    # legacy sync
    send_push(device_token="...", title="Новый микс", body="...")
    # batch async (call from asyncio.run(...))
    count = await send_push_fanout_async(db, [uid1, uid2, ...], "Title", "Body")
"""

import asyncio
import json
import logging
import os
import time
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

_jwt_cache: dict = {"token": None, "issued_at": 0}

# ---------------------------------------------------------------------------
# Persistent async HTTP/2 client — reused across all push calls in process.
# ---------------------------------------------------------------------------
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(http2=True, timeout=10.0)
    return _client


# ---------------------------------------------------------------------------
# JWT helpers (unchanged — sync, cheap)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Core async send — one device token
# ---------------------------------------------------------------------------

async def send_push_async(
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
    """Send APNs push to a single device token. Never raises — returns False on error."""
    if not _is_configured():
        logger.warning("APNs not configured; skipping push to %s", device_token[:12])
        return False
    token = _get_jwt()
    if not token:
        return False

    aps_body: dict = {
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
        # Custom keys go alongside "aps", not inside.
        aps_body.update(payload)

    headers = {
        "authorization": f"bearer {token}",
        "apns-topic": apns_topic or APNS_BUNDLE_ID,
        "apns-priority": str(priority),
        "apns-push-type": "alert",
    }
    url = f"{APNS_HOST}/3/device/{device_token}"

    try:
        client = _get_client()
        resp = await client.post(url, headers=headers, content=json.dumps(aps_body))
        if resp.status_code == 200:
            return True
        logger.warning(
            "APNs %s for %s: %s",
            resp.status_code, device_token[:12], resp.text[:200],
        )
        return False
    except Exception as e:
        logger.error("APNs request failed for %s: %s", device_token[:12], e)
        return False


# ---------------------------------------------------------------------------
# Sync wrapper — legacy callers (single push)
# ---------------------------------------------------------------------------

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
    """Sync wrapper for legacy callers. For batch use send_push_fanout_async."""
    return asyncio.run(
        send_push_async(
            device_token, title, body,
            badge=badge, sound=sound, category=category,
            payload=payload, priority=priority, apns_topic=apns_topic,
        )
    )


# ---------------------------------------------------------------------------
# Fan-out: all tokens of one user
# ---------------------------------------------------------------------------

async def send_push_to_user_async(
    db,
    user_id: int,
    title: str,
    body: str,
    **kwargs,
) -> int:
    """Send push to every device token belonging to user_id. Returns success count."""
    from app.models import DeviceToken  # local import to avoid cycle on cold start

    rows = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    if not rows:
        return 0
    tasks = [send_push_async(r.token, title, body, **kwargs) for r in rows]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return sum(1 for r in results if r is True)


def send_push_to_user(db, user_id: int, title: str, body: str, **kwargs) -> int:
    """Sync wrapper — fan-out to all tokens of one user."""
    return asyncio.run(send_push_to_user_async(db, user_id, title, body, **kwargs))


# ---------------------------------------------------------------------------
# Fan-out: list of user_ids — single asyncio.gather across ALL tokens
# ---------------------------------------------------------------------------

async def send_push_fanout_async(
    db,
    user_ids: list,
    title: str,
    body: str,
    **kwargs,
) -> int:
    """Fan-out push to all device tokens for a list of user_ids.

    Fires all HTTP/2 requests concurrently via asyncio.gather — single
    persistent connection to APNs, multiplexed streams.
    Returns total success count.
    """
    from app.models import DeviceToken  # local import to avoid cycle

    if not user_ids:
        return 0
    rows = (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id.in_(user_ids))
        .limit(5000)
        .all()
    )
    if not rows:
        return 0
    tasks = [send_push_async(r.token, title, body, **kwargs) for r in rows]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return sum(1 for r in results if r is True)
