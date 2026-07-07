"""
Lounge billing subscriptions helper — Sprint 1, 2026-05-27.

get_active_tier(db, brand_id) -> str
    Returns the current paid/trial tier for a lounge.
    Picks the row with the latest expires_at that is still in the future
    and has status in ('active', 'trialing').
    Falls back to 'start' when nothing is active.

require_tier(db, brand_id, minimum) -> None
    Raises HTTPException(402) if the lounge's active tier is below `minimum`.
    Tier order: start < lite < pro < network < partner.

check_event_limit(db, brand_id) -> None
    Raises HTTPException(402) if the lounge already has >= EVENT_LIMITS[tier]
    active afisha events for its current billing tier (G1, 2026-07-07).
    A tier limit of None means unlimited.

check_push_limit(db, brand_id) -> None
    Raises HTTPException(402) if the lounge's tier has no subscriber-push
    access at all (start), or the lounge already sent >= PUSH_LIMITS[tier]
    broadcast pushes this calendar month (G2, 2026-07-07).
    A tier limit of None means unlimited; 0 means no access.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    pass

# Ordered tier list — index = tier rank (higher = better)
TIER_ORDER = ["start", "lite", "pro", "network", "partner"]

# Active-events cap per tier — afisha gate (G1, 2026-07-07). None = unlimited.
EVENT_LIMITS = {"start": 1, "lite": 3, "pro": None, "network": None, "partner": None}

# Monthly subscriber-push cap per tier — push gate (G2, 2026-07-07).
# 0 = no access at all (start); None = unlimited (network, partner).
PUSH_LIMITS = {"start": 0, "lite": 2, "pro": 8, "network": None, "partner": None}


def _tier_rank(tier: str) -> int:
    try:
        return TIER_ORDER.index(tier)
    except ValueError:
        return 0  # unknown tier → treat as start


def get_active_tier(db: Session, brand_id: str) -> str:
    """Return the active billing tier for a lounge, or 'start' if none."""
    # Import here to avoid circular import at module level
    from app.models import LoungeBillingSubscription

    now = datetime.utcnow()
    row = (
        db.query(LoungeBillingSubscription)
        .filter(
            LoungeBillingSubscription.brand_id == brand_id,
            LoungeBillingSubscription.expires_at > now,
            LoungeBillingSubscription.status.in_(["active", "trialing"]),
        )
        .order_by(LoungeBillingSubscription.expires_at.desc())
        .first()
    )
    if row is None:
        return "start"
    return row.tier


def require_tier(db: Session, brand_id: str, minimum: str) -> None:
    """
    Raise HTTP 402 with structured body if the lounge's active tier is
    below `minimum`.

    Usage in endpoint:
        require_tier(db, brand_id, "pro")
    """
    current = get_active_tier(db, brand_id)
    if _tier_rank(current) < _tier_rank(minimum):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "upgrade_required",
                "required_tier": minimum,
                "current_tier": current,
            },
        )


def check_event_limit(db: Session, brand_id: str) -> None:
    """
    Raise HTTP 402 if the lounge is already at (or over) its active-events
    cap for the current billing tier.

    "Active" = Event.lounge_id == brand_id AND
               (Event.ends_at IS NULL OR Event.ends_at > now()).
    A tier with EVENT_LIMITS[tier] is None is treated as unlimited and
    always passes without querying the count.

    Usage in endpoint (after can_manage_brand, before creating the Event):
        if not current_user.is_admin:
            check_event_limit(db, brand_id)
    """
    # Import here to avoid circular import at module level (see get_active_tier).
    from app.models import Event

    tier = get_active_tier(db, brand_id)
    limit = EVENT_LIMITS.get(tier)
    if limit is None:
        return  # unlimited on this tier

    now = datetime.utcnow()
    active_count = (
        db.query(func.count(Event.id))
        .filter(
            Event.lounge_id == brand_id,
            (Event.ends_at == None) | (Event.ends_at > now),  # noqa: E711
        )
        .scalar()
    )
    if active_count >= limit:
        required_tier = next(
            (
                t
                for t in TIER_ORDER
                if EVENT_LIMITS.get(t) is None or EVENT_LIMITS[t] > limit
            ),
            "lite",
        )
        raise HTTPException(
            status_code=402,
            detail={
                "error": "upgrade_required",
                "required_tier": required_tier,
                "current_tier": tier,
            },
        )


def check_push_limit(db: Session, brand_id: str) -> None:
    """
    Raise HTTP 402 if the lounge's tier has no subscriber-push access at all
    (start), or the lounge has already sent >= PUSH_LIMITS[tier] broadcast
    pushes in the current calendar month for its billing tier (G2,
    2026-07-07). A tier limit of None means unlimited and always passes
    without querying the count.

    Month boundary is UTC (datetime.utcnow(), same convention used by
    get_active_tier/check_event_limit elsewhere in this module) — "current
    calendar month" = LoungePushLog.sent_at >= first instant of the current
    UTC month.

    Usage in endpoint (after can_manage_brand, before sending the push):
        if not current_user.is_admin:
            check_push_limit(db, brand_id)
    """
    # Import here to avoid circular import at module level (see get_active_tier).
    from app.models import LoungePushLog

    tier = get_active_tier(db, brand_id)
    limit = PUSH_LIMITS.get(tier)

    if limit == 0:
        # start (or any unrecognised tier) — no push access at all.
        raise HTTPException(
            status_code=402,
            detail={
                "error": "upgrade_required",
                "required_tier": "lite",
                "current_tier": tier,
                "message": "Рассылка пушей подписчикам недоступна на тарифе Start — оформите Lite или выше.",
            },
        )
    if limit is None:
        return  # unlimited on this tier

    month_start = datetime.utcnow().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    sent_this_month = (
        db.query(func.count(LoungePushLog.id))
        .filter(
            LoungePushLog.brand_id == brand_id,
            LoungePushLog.sent_at >= month_start,
        )
        .scalar()
    )
    if sent_this_month >= limit:
        required_tier = next(
            (
                t
                for t in TIER_ORDER
                if PUSH_LIMITS.get(t) is None or (PUSH_LIMITS[t] or 0) > limit
            ),
            "pro",
        )
        raise HTTPException(
            status_code=402,
            detail={
                "error": "upgrade_required",
                "required_tier": required_tier,
                "current_tier": tier,
                "message": (
                    f"Лимит пушей на тарифе {tier} исчерпан "
                    f"({sent_this_month}/{limit} в этом месяце)."
                ),
            },
        )
