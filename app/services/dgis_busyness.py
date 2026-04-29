"""
2GIS Catalog API client — fetches real-time venue congestion ("загруженность").

API docs: https://docs.2gis.com/ru/api/search/places/reference/3.0/items
Auth: query param ?key=DGIS_API_KEY (get demo key at platform.2gis.ru).

Two lookup modes:
  1. By branch ID — most reliable. Requires dgis_branch_id stored on the lounge.
  2. By address text — fallback. Searches catalog and takes the first branch.

Returns None when:
  - DGIS_API_KEY not configured
  - Network/HTTP error
  - Venue has has_dynamic_congestion=false (no live data for this branch)
  - congestion field missing or unparseable

The caller is expected to fall through to its next data source on None.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core.config import DGIS_API_KEY

logger = logging.getLogger(__name__)

_BASE_URL = "https://catalog.api.2gis.com/3.0/items"
_TIMEOUT_SECONDS = 4.0
_FIELDS = "items.point,items.address_name,items.has_dynamic_congestion,items.congestion"


def _normalize_congestion(raw) -> Optional[int]:
    """
    2GIS docs do not publish the congestion scale. Empirically it's a string
    that's either a 0-10 integer or a level keyword. Normalize to 0-100.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        n = float(raw)
        if n <= 10:
            return max(0, min(100, int(round(n * 10))))
        return max(0, min(100, int(round(n))))
    if isinstance(raw, str):
        s = raw.strip().lower()
        if not s:
            return None
        try:
            n = float(s)
            if n <= 10:
                return max(0, min(100, int(round(n * 10))))
            return max(0, min(100, int(round(n))))
        except ValueError:
            pass
        if s in {"low", "quiet", "low_load", "free"}:
            return 20
        if s in {"medium", "moderate", "average"}:
            return 55
        if s in {"high", "busy", "loaded"}:
            return 80
        if s in {"peak", "very_high", "overloaded"}:
            return 95
    return None


def _parse_first_item(payload: dict) -> Optional[int]:
    items = (payload.get("result") or {}).get("items") or []
    if not items:
        return None
    item = items[0]
    if not item.get("has_dynamic_congestion"):
        return None
    return _normalize_congestion(item.get("congestion"))


def fetch_congestion_by_branch_id(branch_id: str) -> Optional[int]:
    """Fetch congestion for a known 2GIS branch ID. Returns 0-100 or None."""
    if not DGIS_API_KEY or not branch_id:
        return None
    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            r = client.get(
                f"{_BASE_URL}/byid",
                params={"id": branch_id, "fields": _FIELDS, "key": DGIS_API_KEY},
            )
        if r.status_code != 200:
            logger.warning("2gis byid status=%s body=%s", r.status_code, r.text[:200])
            return None
        return _parse_first_item(r.json())
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("2gis byid error: %s", exc)
        return None


def fetch_congestion_by_address(address: str) -> Optional[int]:
    """Search 2GIS catalog by address text and return congestion of the first branch."""
    if not DGIS_API_KEY or not address:
        return None
    try:
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            r = client.get(
                _BASE_URL,
                params={
                    "q": address,
                    "type": "branch",
                    "fields": _FIELDS,
                    "key": DGIS_API_KEY,
                    "page_size": 1,
                },
            )
        if r.status_code != 200:
            logger.warning("2gis search status=%s body=%s", r.status_code, r.text[:200])
            return None
        return _parse_first_item(r.json())
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("2gis search error: %s", exc)
        return None
