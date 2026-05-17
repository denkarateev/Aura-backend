"""
LOOMIX-parity leaderboard / medals service.

The "Top забивок" feature ranks mixes by likes received during a calendar
period (week or month, MSK timezone). Top-3 ranks get gold/silver/bronze
medals on the user profile, awarded automatically by APScheduler on the
first day of the next period.

Period definitions (all in Europe/Moscow):
    week:  Monday 00:00 — next Monday 00:00 (exclusive). period_start is
           the Monday DATE of that range.
    month: 1st day 00:00 — 1st day of next month 00:00 (exclusive).
           period_start is the 1st of that month.

The service is import-safe: it only uses SQLAlchemy + stdlib. The actual
APScheduler binding lives in main.py startup so we share a single
scheduler instance per FastAPI worker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

try:
    # Available on Python 3.9+; project runs on 3.11 in Docker.
    from zoneinfo import ZoneInfo
    MSK_TZ = ZoneInfo("Europe/Moscow")
except Exception:  # pragma: no cover — fallback to fixed +03:00
    from datetime import timezone
    MSK_TZ = timezone(timedelta(hours=3))

from app.models import Favorite, Mix, User, UserMedal

logger = logging.getLogger(__name__)

MEDALS_BY_RANK = {1: "gold", 2: "silver", 3: "bronze"}


# ---------------------------------------------------------------------------
# Period math (MSK-aware)
# ---------------------------------------------------------------------------

def _msk_now() -> datetime:
    return datetime.now(MSK_TZ)


def week_bounds(reference: Optional[datetime] = None) -> tuple[datetime, datetime, date]:
    """Return (start_dt, end_dt, period_start_date) for the week the
    `reference` MSK datetime falls into. Monday-start, Sunday end-of-day.
    end_dt is exclusive (next Monday 00:00 MSK)."""
    ref = reference or _msk_now()
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=MSK_TZ)
    monday = ref - timedelta(days=ref.weekday())
    start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end, start.date()


def prev_week_bounds(reference: Optional[datetime] = None) -> tuple[datetime, datetime, date]:
    """Week that just ended: previous Monday 00:00 — this Monday 00:00."""
    start, _, _ = week_bounds(reference)
    prev_start = start - timedelta(days=7)
    return prev_start, start, prev_start.date()


def month_bounds(reference: Optional[datetime] = None) -> tuple[datetime, datetime, date]:
    """Return (start_dt, end_dt, period_start_date) for the calendar month
    containing `reference` (MSK)."""
    ref = reference or _msk_now()
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=MSK_TZ)
    start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # First day of next month
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end, start.date()


def prev_month_bounds(reference: Optional[datetime] = None) -> tuple[datetime, datetime, date]:
    """Calendar month that just ended."""
    start, _, _ = month_bounds(reference)
    prev_end = start
    # Previous month is one day before start, then snap to day=1.
    prev_month_anchor = start - timedelta(days=1)
    prev_start = prev_month_anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return prev_start, prev_end, prev_start.date()


def bounds_for(period: str, reference: Optional[datetime] = None) -> tuple[datetime, datetime, date]:
    if period == "week":
        return week_bounds(reference)
    if period == "month":
        return month_bounds(reference)
    raise ValueError(f"Unsupported period: {period}")


def prev_bounds_for(period: str, reference: Optional[datetime] = None) -> tuple[datetime, datetime, date]:
    if period == "week":
        return prev_week_bounds(reference)
    if period == "month":
        return prev_month_bounds(reference)
    raise ValueError(f"Unsupported period: {period}")


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RankedRow:
    mix: Mix
    likes_count: int


def top_mixes_in_window(
    db: Session,
    start_dt: datetime,
    end_dt: datetime,
    limit: int = 10,
) -> List[RankedRow]:
    """Mixes ranked by number of LIKES RECEIVED in [start_dt, end_dt).

    Это LOOMIX-style ranking: «топ забивок недели» = миксы которым ставят
    лайки именно в этот период. Микс может быть создан год назад — если
    его лайкают на этой неделе, он попадёт в подиум. Это интуитивнее
    чем «миксы созданные за неделю» (старая версия) и даёт работающий
    leaderboard даже когда новых миксов мало.

    Both naive (UTC) and tz-aware datetimes are accepted — we strip
    tzinfo so the comparison works against Favorite.created_at which is
    stored as naive UTC (default=datetime.utcnow).
    """
    if start_dt.tzinfo is not None:
        # MSK -> naive UTC (MSK = UTC+3, no DST).
        start_dt = start_dt.astimezone(MSK_TZ).replace(tzinfo=None) - timedelta(hours=3)
    if end_dt.tzinfo is not None:
        end_dt = end_dt.astimezone(MSK_TZ).replace(tzinfo=None) - timedelta(hours=3)

    # Период-фильтр на Favorite.created_at (а не Mix.created_at).
    # Используем sum(case when in_period) — так INNER JOIN отсекает
    # миксы без единого лайка в окне, что нам и нужно для «топ недели».
    period_likes = (
        db.query(
            Favorite.mix_id.label("mid"),
            func.count(Favorite.id).label("likes_in_period"),
        )
        .filter(Favorite.created_at >= start_dt, Favorite.created_at < end_dt)
        .group_by(Favorite.mix_id)
        .subquery()
    )

    rows = (
        db.query(Mix, period_likes.c.likes_in_period)
        .join(period_likes, period_likes.c.mid == Mix.id)
        .filter((Mix.status == "public") | (Mix.status.is_(None)))
        .order_by(period_likes.c.likes_in_period.desc(), Mix.created_at.desc(), Mix.id.asc())
        .limit(limit)
        .all()
    )

    return [RankedRow(mix=mix, likes_count=int(likes or 0)) for mix, likes in rows]


# ---------------------------------------------------------------------------
# Medal grant (idempotent)
# ---------------------------------------------------------------------------

def grant_medals_for_period(
    db: Session,
    period_type: str,
    reference: Optional[datetime] = None,
) -> dict:
    """Compute top-3 of the previous {period_type} and insert UserMedal
    rows for them. Idempotent: re-running on the same period is a no-op
    thanks to the unique constraint (user_id, period_type, period_start,
    medal_type).

    Returns a small summary dict for logging / admin response.
    """
    if period_type not in {"week", "month"}:
        raise ValueError("period_type must be 'week' or 'month'")

    start_dt, end_dt, period_start = prev_bounds_for(period_type, reference)
    top = top_mixes_in_window(db, start_dt, end_dt, limit=3)

    granted = 0
    skipped = 0
    inserted_entries: list[dict] = []
    for idx, row in enumerate(top, start=1):
        medal_type = MEDALS_BY_RANK.get(idx)
        if not medal_type:
            continue
        author_id = row.mix.author_id
        if not author_id:
            continue
        medal = UserMedal(
            user_id=author_id,
            medal_type=medal_type,
            period_type=period_type,
            period_start=period_start,
            mix_id=row.mix.id,
            likes_count=row.likes_count,
        )
        db.add(medal)
        try:
            db.flush()
            granted += 1
            inserted_entries.append(
                {
                    "rank": idx,
                    "medal": medal_type,
                    "mix_id": row.mix.id,
                    "user_id": author_id,
                    "likes_count": row.likes_count,
                }
            )
        except IntegrityError:
            db.rollback()
            skipped += 1
            logger.info(
                "grant_medals_for_period: skip existing %s medal for user=%s period=%s/%s",
                medal_type, author_id, period_type, period_start,
            )
    db.commit()
    logger.info(
        "grant_medals_for_period: period=%s start=%s granted=%d skipped=%d",
        period_type, period_start, granted, skipped,
    )
    return {
        "period_type": period_type,
        "period_start": period_start,
        "granted": granted,
        "skipped": skipped,
        "entries": inserted_entries,
    }


# ---------------------------------------------------------------------------
# Profile stats
# ---------------------------------------------------------------------------

def user_public_stats(db: Session, user: User) -> dict:
    """Aggregate counters for the per-user profile header. Uses simple
    COUNT/SUM queries — fast enough for our scale (≤ a few hundred mixes
    per user)."""
    from app.models import Comment, UserFollow

    posts_count = (
        db.query(func.count(Mix.id))
        .filter(Mix.author_id == user.id)
        .scalar()
        or 0
    )

    likes_received = (
        db.query(func.count(Favorite.id))
        .join(Mix, Mix.id == Favorite.mix_id)
        .filter(Mix.author_id == user.id)
        .scalar()
        or 0
    )

    comments_made = (
        db.query(func.count(Comment.id))
        .filter(Comment.user_id == user.id)
        .scalar()
        or 0
    )

    followers_count = (
        db.query(func.count(UserFollow.id))
        .filter(UserFollow.following_id == user.id)
        .scalar()
        or 0
    )

    following_count = (
        db.query(func.count(UserFollow.id))
        .filter(UserFollow.follower_id == user.id)
        .scalar()
        or 0
    )

    medal_rows = (
        db.query(UserMedal.medal_type, func.count(UserMedal.id))
        .filter(UserMedal.user_id == user.id)
        .group_by(UserMedal.medal_type)
        .all()
    )
    medals = {"gold": 0, "silver": 0, "bronze": 0}
    for medal_type, count in medal_rows:
        if medal_type in medals:
            medals[medal_type] = int(count)

    return {
        "posts_count": int(posts_count),
        "likes_received": int(likes_received),
        "comments_made": int(comments_made),
        "followers_count": int(followers_count),
        "following_count": int(following_count),
        "medals": medals,
    }
