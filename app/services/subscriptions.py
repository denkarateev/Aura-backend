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
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    pass

# Ordered tier list — index = tier rank (higher = better)
TIER_ORDER = ["start", "lite", "pro", "network", "partner"]


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
