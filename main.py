import uuid
import random
import string
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
import hashlib
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func
from jose import jwt
from sqlalchemy.orm import Session, joinedload

from app.core.config import (
    ALGORITHM,
    BUNDLE_TIERS,
    DEFAULT_BRAND_MANAGER_USERNAMES,
    BOWL_HEAT_DURATION_SECONDS,
    BOWL_HEAT_TARGET_SCORE,
    DEFAULT_ADMIN_EMAILS,
    DEFAULT_ADMIN_USERNAMES,
    DEFAULT_UNLIMITED_MIX_EMAILS,
    DEFAULT_UNLIMITED_MIX_USERNAMES,
    MAX_BOWL_HEAT_ATTEMPTS,
    MIX_SLOT_RULES,
    RATING_LEVELS,
    REWARD_RULES,
    SECRET_KEY,
    YOOKASSA_RETURN_URL,
    YOOKASSA_SECRET_KEY,
    YOOKASSA_SHOP_ID,
    load_brand_manager_usernames,
)
from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, security
from app.models import (
    Duel,
    BowlHeatRun,
    Comment,
    Favorite,
    LoungeAssets,
    LoungeBundle,
    LoungeBundleVisit,
    LoungeBusinessEvent,
    LoungeGuestLoyalty,
    LoungeGuestPersonalization,
    DeviceToken,
    LoungeLedgerEntry,
    LoungeProgram,
    Mix,
    MixIngredient,
    MonthlyVote,
    User,
    UserActivity,
    UserFollow,
    UserProgress,
)
from app.schemas import (
    DuelCreateIn,
    DuelCreateOut,
    DuelJoinIn,
    DuelStateOut,
    AdminBanIn,
    AdminDashboardOut,
    AdminDashboardStatsOut,
    AdminMixRowOut,
    AdminUserRowOut,
    BowlHeatGameStateOut,
    BowlHeatPlayIn,
    BowlHeatPlayOut,
    BundleListOut,
    BundleOut,
    BundlePaymentCreateIn,
    BundlePaymentCreateOut,
    BundlePaymentStatusOut,
    BundleRecentVisitOut,
    BundleRedemptionOut,
    BundleVisitOut,
    AppleSignInIn,
    AppleSignInOut,
    DeviceTokenIn,
    CommentIn,
    CommentOut,
    FollowToggleOut,
    FollowUserOut,
    IngredientOut,
    LoginRequest,
    LoginResponse,
    LoungeAnalyticsDayOut,
    LoungeAnalyticsOut,
    LoungeCheckinIn,
    LoungeCheckinOut,
    LoungeGuestRecordIn,
    LoungeGuestRecordOut,
    LoungeMyLoyaltyOut,
    LoungeProgramIn,
    LoungeProgramOut,
    LoungeTierOut,
    MixCreate,
    MixOut,
    MonthlyFlavorOut,
    ProfileCommentOut,
    SignupRequest,
    StatusOut,
    UserActivityOut,
    UserSearchOut,
    WalletConnectIn,
    WalletBalanceOut,
    WalletMintOut,
    WalletBurnOut,
    UserOut,
    UserProgressOut,
    UserUpdate,
    VoteMixOut,
    LoungeAssetsIn,
    LoungeAssetsOut,
)

# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hash_):
    return hash_password(password) == hash_


def normalized_allowlist(name: str, defaults: set[str]) -> set[str]:
    raw_value = os.getenv(name)
    if not raw_value:
        return {item.lower() for item in defaults}

    return {
        item.strip().lower()
        for item in raw_value.split(",")
        if item.strip()
    }


def user_matches_admin_allowlist(user: User) -> bool:
    admin_emails = normalized_allowlist("ADMIN_EMAILS", DEFAULT_ADMIN_EMAILS)
    admin_usernames = normalized_allowlist("ADMIN_USERNAMES", DEFAULT_ADMIN_USERNAMES)

    email = (user.email or "").strip().lower()
    username = (user.username or "").strip().lower()

    return email in admin_emails or username in admin_usernames


def sync_admin_allowlist(db: Session):
    users = db.query(User).all()
    did_change = False

    for user in users:
        if user_matches_admin_allowlist(user) and not user.is_admin:
            user.is_admin = True
            did_change = True

    if did_change:
        db.commit()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not creds:
        return None

    try:
        payload = jwt.decode(
            creds.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        user_id = int(payload["sub"])
    except Exception:
        return None

    user = db.query(User).options(
        joinedload(User.mixes)
        .joinedload(Mix.ingredients),
        joinedload(User.favorites)
        .joinedload(Favorite.mix)
        .joinedload(Mix.ingredients),
        joinedload(User.comments)
        .joinedload(Comment.mix)
    ).get(user_id)

    if user and user.is_banned:
        detail = user.ban_reason or "Account banned"
        raise HTTPException(403, detail)

    return user


def get_admin_user(
    user: User = Depends(get_current_user)
) -> User:
    if not user:
        raise HTTPException(401, "Unauthorized")
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user


def mix_to_out(mix: Mix, user: Optional[User], db: Session):
    likes_count = db.query(Favorite)\
        .filter(Favorite.mix_id == mix.id).count()

    is_liked = False
    if user:
        is_liked = db.query(Favorite)\
            .filter(
                Favorite.mix_id == mix.id,
                Favorite.user_id == user.id
            ).first() is not None

    is_author_followed = False
    if user and mix.author_id and mix.author_id != user.id:
        is_author_followed = db.query(UserFollow).filter(
            UserFollow.follower_id == user.id,
            UserFollow.following_id == mix.author_id
        ).first() is not None

    return MixOut(
        id=mix.id,
        name=mix.name,
        mood=mix.mood,
        intensity=mix.intensity,
        description=mix.description,
        bowl_type=mix.bowl_type,
        packing_style=mix.packing_style,
        bowl_image_name=mix.bowl_image_name,
        author_id=mix.author_id,
        author_username=mix.author.username if mix.author else None,
        created_at=mix.created_at,
        ingredients=mix.ingredients,
        likes_count=likes_count,
        is_liked=is_liked,
        is_author_followed=is_author_followed
    )


def comment_to_profile_out(comment: Comment):
    return ProfileCommentOut(
        id=comment.id,
        mix_id=comment.mix_id,
        user_id=comment.user_id,
        user_username=comment.user.username if comment.user else None,
        text=comment.text,
        mix_name=comment.mix.name if comment.mix else None,
        created_at=comment.created_at
    )


def comment_to_out(comment: Comment) -> CommentOut:
    return CommentOut(
        id=comment.id,
        mix_id=comment.mix_id,
        user_id=comment.user_id,
        user_username=comment.user.username if comment.user else None,
        text=comment.text,
        created_at=comment.created_at
    )


def level_title_for_rating(rating: int) -> str:
    title = RATING_LEVELS[0][1]
    for threshold, candidate in RATING_LEVELS:
        if rating >= threshold:
            title = candidate
        else:
            break
    return title


def next_level_rating_for(rating: int) -> int:
    for threshold, _ in RATING_LEVELS:
        if threshold > rating:
            return threshold
    return RATING_LEVELS[-1][0]


def mix_slots_for_rating(rating: int) -> int:
    slots = MIX_SLOT_RULES[0][1]
    for threshold, candidate in MIX_SLOT_RULES:
        if rating >= threshold:
            slots = candidate
        else:
            break
    return slots


def next_mix_slot_threshold_for(rating: int) -> Optional[int]:
    current_slots = mix_slots_for_rating(rating)
    for threshold, slots in MIX_SLOT_RULES:
        if threshold > rating and slots > current_slots:
            return threshold
    return None


def russian_mix_word(count: int) -> str:
    last_two_digits = count % 100
    last_digit = count % 10

    if 11 <= last_two_digits <= 14:
        return "миксов"
    if last_digit == 1:
        return "микс"
    if 2 <= last_digit <= 4:
        return "микса"
    return "миксов"


def user_has_unlimited_mix_slots(user: User) -> bool:
    if user.is_admin:
        return True

    unlimited_emails = normalized_allowlist(
        "UNLIMITED_MIX_EMAILS",
        DEFAULT_UNLIMITED_MIX_EMAILS
    )
    unlimited_usernames = normalized_allowlist(
        "UNLIMITED_MIX_USERNAMES",
        DEFAULT_UNLIMITED_MIX_USERNAMES
    )

    email = (user.email or "").strip().lower()
    username = (user.username or "").strip().lower()

    return email in unlimited_emails or username in unlimited_usernames


def mix_slots_state_for_user(user: User, db: Session) -> dict:
    progress = ensure_user_progress(user, db)
    rating = progress.rating or 0
    mixes_used = db.query(Mix).filter(Mix.author_id == user.id).count()
    has_unlimited = user_has_unlimited_mix_slots(user)

    if has_unlimited:
        return {
            "mixes_used": mixes_used,
            "max_mix_slots": None,
            "mixes_remaining": None,
            "has_unlimited_mix_slots": True,
            "next_threshold": None,
        }

    max_mix_slots = mix_slots_for_rating(rating)
    return {
        "mixes_used": mixes_used,
        "max_mix_slots": max_mix_slots,
        "mixes_remaining": max(max_mix_slots - mixes_used, 0),
        "has_unlimited_mix_slots": False,
        "next_threshold": next_mix_slot_threshold_for(rating),
    }


def ensure_user_progress(user: User, db: Session) -> UserProgress:
    progress = user.progress
    if progress:
        return progress

    progress = db.query(UserProgress).filter(
        UserProgress.user_id == user.id
    ).first()
    if progress:
        user.progress = progress
        return progress

    progress = UserProgress(user_id=user.id)
    db.add(progress)
    db.flush()
    user.progress = progress
    return progress


def progress_to_out(progress: UserProgress, user: User, db: Session) -> UserProgressOut:
    rating = progress.rating or 0
    mix_slots_state = mix_slots_state_for_user(user, db)
    return UserProgressOut(
        points=progress.points or 0,
        rating=rating,
        streak_days=progress.streak_days or 0,
        level_title=level_title_for_rating(rating),
        next_level_rating=next_level_rating_for(rating),
        mixes_used=mix_slots_state["mixes_used"],
        max_mix_slots=mix_slots_state["max_mix_slots"],
        mixes_remaining=mix_slots_state["mixes_remaining"],
        has_unlimited_mix_slots=mix_slots_state["has_unlimited_mix_slots"]
    )


def activity_to_out(activity: UserActivity) -> UserActivityOut:
    return UserActivityOut(
        id=activity.id,
        event_type=activity.event_type,
        title=activity.title,
        description=activity.description,
        points_delta=activity.points_delta,
        rating_delta=activity.rating_delta,
        created_at=activity.created_at
    )


def record_progress_event(
    user: Optional[User],
    db: Session,
    event_type: str,
    title: str,
    description: Optional[str],
    points_delta: int,
    rating_delta: int
):
    if not user:
        return None

    progress = ensure_user_progress(user, db)
    progress.points += points_delta
    progress.rating += rating_delta
    progress.updated_at = datetime.utcnow()

    activity = UserActivity(
        user_id=user.id,
        event_type=event_type,
        title=title,
        description=description,
        points_delta=points_delta,
        rating_delta=rating_delta
    )
    db.add(activity)
    db.flush()
    return activity


def award_event(
    user: Optional[User],
    event_type: str,
    db: Session,
    description: Optional[str] = None,
    title: Optional[str] = None
):
    if not user:
        return None

    rule = REWARD_RULES.get(event_type)
    if not rule:
        return None

    today = datetime.utcnow().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = start_of_day + timedelta(days=1)

    daily_count = db.query(UserActivity).filter(
        UserActivity.user_id == user.id,
        UserActivity.event_type == event_type,
        UserActivity.created_at >= start_of_day,
        UserActivity.created_at < end_of_day
    ).count()

    if daily_count >= rule["daily_limit"]:
        return None

    return record_progress_event(
        user=user,
        db=db,
        event_type=event_type,
        title=title or rule["title"],
        description=description,
        points_delta=rule["points"],
        rating_delta=rule["rating"]
    )


def track_daily_login(user: User, db: Session):
    progress = ensure_user_progress(user, db)
    today = datetime.utcnow().date()

    if progress.last_active_date == today:
        return progress

    if progress.last_active_date == today - timedelta(days=1):
        progress.streak_days += 1
    else:
        progress.streak_days = 1

    progress.last_active_date = today
    progress.updated_at = datetime.utcnow()

    award_event(
        user,
        "daily_login",
        db,
        description=f"Серия входов: {progress.streak_days} д."
    )
    return progress


def current_day_bounds() -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    day_start = datetime(now.year, now.month, now.day)
    return day_start, day_start + timedelta(days=1)


def bowl_heat_reward_for_score(score: int) -> dict:
    normalized_score = max(min(score, 100), 0)
    if normalized_score >= 85:
        return {
            "tier": "Идеальный прогрев",
            "points": 20,
            "rating": 2,
            "title": "Идеальный прогрев",
            "message": "Ты держал жар почти идеально. Такая попытка уже работает на статус.",
        }
    if normalized_score >= 65:
        return {
            "tier": "Сочный прогрев",
            "points": 12,
            "rating": 1,
            "title": "Сочный прогрев",
            "message": "Хороший контроль жара. Ещё немного стабильности и это будет идеальный сет.",
        }
    if normalized_score >= 40:
        return {
            "tier": "Ровный старт",
            "points": 6,
            "rating": 0,
            "title": "Ровный старт",
            "message": "Чаша уже живёт, но сладкую зону пока держишь недолго.",
        }
    return {
        "tier": "Нужна практика",
        "points": 2,
        "rating": 0,
        "title": "Нужна практика",
        "message": "Попробуй мягче держать жар и не уходить в перегрев.",
    }


def build_bowl_heat_state(user: User, db: Session) -> BowlHeatGameStateOut:
    day_start, day_end = current_day_bounds()
    runs = db.query(BowlHeatRun).filter(
        BowlHeatRun.user_id == user.id,
        BowlHeatRun.created_at >= day_start,
        BowlHeatRun.created_at < day_end
    ).order_by(
        BowlHeatRun.created_at.desc(),
        BowlHeatRun.id.desc()
    ).all()

    best_score_today = max((run.score for run in runs), default=0)
    best_tier_today = bowl_heat_reward_for_score(best_score_today)["tier"] if best_score_today > 0 else None
    last_played_at = runs[0].created_at if runs else None
    attempts_used = len(runs)
    attempts_left = max(MAX_BOWL_HEAT_ATTEMPTS - attempts_used, 0)

    return BowlHeatGameStateOut(
        title="Дневной прогрев",
        subtitle="Двигай уголь по чаше, держи жар в зелёной зоне и забирай лучшую награду за день.",
        attempts_used=attempts_used,
        attempts_left=attempts_left,
        max_attempts=MAX_BOWL_HEAT_ATTEMPTS,
        best_score_today=best_score_today,
        best_tier_today=best_tier_today,
        target_score=BOWL_HEAT_TARGET_SCORE,
        duration_seconds=BOWL_HEAT_DURATION_SECONDS,
        reward_hint="Лучшая попытка дня приносит до 20 баллов и 2 рейтинга.",
        can_play=attempts_left > 0,
        last_played_at=last_played_at
    )


def follow_user_to_out(target_user: User, viewer: Optional[User], db: Session) -> FollowUserOut:
    latest_mix = db.query(Mix).filter(
        Mix.author_id == target_user.id
    ).order_by(
        Mix.created_at.desc(),
        Mix.id.desc()
    ).first()

    mixes_count = db.query(Mix).filter(Mix.author_id == target_user.id).count()
    likes_count = db.query(Favorite).join(
        Mix, Favorite.mix_id == Mix.id
    ).filter(
        Mix.author_id == target_user.id
    ).count()

    is_following = False
    if viewer and viewer.id != target_user.id:
        is_following = db.query(UserFollow).filter(
            UserFollow.follower_id == viewer.id,
            UserFollow.following_id == target_user.id
        ).first() is not None

    return FollowUserOut(
        id=target_user.id,
        username=target_user.username,
        mixes_count=mixes_count,
        likes_count=likes_count,
        latest_mix_id=latest_mix.id if latest_mix else None,
        latest_mix_name=latest_mix.name if latest_mix else None,
        latest_mix_bowl_image_name=latest_mix.bowl_image_name if latest_mix else None,
        latest_mix_created_at=latest_mix.created_at if latest_mix else None,
        is_following=is_following
    )


def user_to_out(profile_user: User, viewer: Optional[User], db: Session) -> UserOut:
    favorites = [favorite.mix for favorite in profile_user.favorites if favorite.mix]
    progress = ensure_user_progress(profile_user, db)
    activity_feed = db.query(UserActivity).filter(
        UserActivity.user_id == profile_user.id
    ).order_by(
        UserActivity.created_at.desc(),
        UserActivity.id.desc()
    ).limit(10).all()
    following_links = db.query(UserFollow).options(
        joinedload(UserFollow.following)
    ).filter(
        UserFollow.follower_id == profile_user.id
    ).order_by(
        UserFollow.id.desc()
    ).all()
    followers_count = db.query(UserFollow).filter(
        UserFollow.following_id == profile_user.id
    ).count()

    return UserOut(
        id=profile_user.id,
        email=profile_user.email,
        username=profile_user.username,
        is_admin=profile_user.is_admin,
        is_banned=profile_user.is_banned,
        ban_reason=profile_user.ban_reason,
        mixes=[mix_to_out(mix, viewer, db) for mix in profile_user.mixes],
        favorites=[mix_to_out(mix, viewer, db) for mix in favorites],
        comments=[comment_to_profile_out(comment) for comment in profile_user.comments],
        progress=progress_to_out(progress, profile_user, db),
        activity_feed=[activity_to_out(activity) for activity in activity_feed],
        daily_game=build_bowl_heat_state(profile_user, db),
        followers_count=followers_count,
        following_count=len(following_links),
        following_users=[
            follow_user_to_out(link.following, viewer, db)
            for link in following_links
            if link.following is not None
        ]
    )


BRAND_MANAGER_USERNAMES = load_brand_manager_usernames()


def normalize_key(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def display_title_from_brand_id(brand_id: str) -> str:
    pieces = [piece for piece in brand_id.replace("-", "_").split("_") if piece]
    if not pieces:
        return "Lounge"
    return " ".join(piece.capitalize() for piece in pieces)


def default_lounge_program_values(brand_id: str) -> dict:
    title = f"{display_title_from_brand_id(brand_id)} Club"
    return {
        "title": title,
        "summary": "Сохраняй визиты, чтобы копить скидку и получать персональные предложения от заведения.",
        "base_discount_percent": 5,
        "welcome_offer_title": f"Welcome в {display_title_from_brand_id(brand_id)}",
        "welcome_offer_body": "Стартовая скидка 5% на первую бронь и быстрый вход в профиль заведения.",
    }


def lounge_tier_for_visits(visits: int) -> LoungeTierOut:
    if visits >= 8:
        return LoungeTierOut(
            title="Signature",
            discount_percent=15,
            discount_text="15%",
            benefit="Приоритет на VIP и закрытые офферы",
            next_goal=None,
        )
    if visits >= 4:
        return LoungeTierOut(
            title="Resident",
            discount_percent=10,
            discount_text="10%",
            benefit="Ранняя бронь и бонус к вечерним слотам",
            next_goal=8,
        )
    if visits >= 1:
        return LoungeTierOut(
            title="Insider",
            discount_percent=7,
            discount_text="7%",
            benefit="Скидка на посадку и персональные офферы",
            next_goal=4,
        )
    return LoungeTierOut(
        title="Welcome",
        discount_percent=5,
        discount_text="5%",
        benefit="Стартовая скидка и welcome-предложение",
        next_goal=1,
    )


def user_search_to_out(user: User) -> UserSearchOut:
    display_name = (user.username or "").strip() or user.email
    return UserSearchOut(
        id=user.id,
        username=user.username or display_name,
        display_name=display_name,
    )


def resolve_brand_managers(brand_id: str) -> set[str]:
    if brand_id in BRAND_MANAGER_USERNAMES:
        return BRAND_MANAGER_USERNAMES[brand_id]
    defaults = DEFAULT_BRAND_MANAGER_USERNAMES.get(brand_id, set())
    return {username.lower() for username in defaults}


def can_manage_brand(user: Optional[User], brand_id: str) -> bool:
    if not user:
        return False
    if user.is_admin:
        return True

    allowed = resolve_brand_managers(brand_id)
    email = normalize_key(user.email)
    username = normalize_key(user.username)
    return username in allowed or email in allowed


def get_required_user(user: Optional[User]) -> User:
    if not user:
        raise HTTPException(401, "Unauthorized")
    return user


def get_lounge_program(brand_id: str, db: Session) -> LoungeProgram | None:
    return db.query(LoungeProgram).filter(LoungeProgram.brand_id == brand_id).first()


def lounge_program_to_out(program: Optional[LoungeProgram], brand_id: str) -> LoungeProgramOut:
    if not program:
        return LoungeProgramOut(
            brand_id=brand_id,
            updated_at=None,
            **default_lounge_program_values(brand_id),
        )

    return LoungeProgramOut(
        brand_id=program.brand_id,
        title=program.title,
        summary=program.summary,
        base_discount_percent=program.base_discount_percent,
        welcome_offer_title=program.welcome_offer_title,
        welcome_offer_body=program.welcome_offer_body,
        updated_at=program.updated_at,
    )


def lounge_personalization_to_out(
    record: LoungeGuestPersonalization,
    guest_user: User,
) -> LoungeGuestRecordOut:
    return LoungeGuestRecordOut(
        id=record.id,
        user_id=guest_user.id,
        username=guest_user.username or guest_user.email,
        display_name=record.display_name or guest_user.username or guest_user.email,
        favorite_order=record.favorite_order,
        average_check=record.average_check,
        visit_count=record.visit_count,
        personal_tier_title=record.personal_tier_title,
        personal_discount_percent=record.personal_discount_percent,
        personal_offer_title=record.personal_offer_title,
        personal_offer_body=record.personal_offer_body,
        note=record.note,
        updated_at=record.updated_at,
    )


def build_lounge_loyalty_out(
    brand_id: str,
    guest_user: User,
    db: Session,
) -> LoungeMyLoyaltyOut:
    program = get_lounge_program(brand_id, db)
    program_out = lounge_program_to_out(program, brand_id)
    loyalty = db.query(LoungeGuestLoyalty).filter(
        LoungeGuestLoyalty.brand_id == brand_id,
        LoungeGuestLoyalty.user_id == guest_user.id,
    ).first()
    personalization = db.query(LoungeGuestPersonalization).filter(
        LoungeGuestPersonalization.brand_id == brand_id,
        LoungeGuestPersonalization.user_id == guest_user.id,
    ).first()

    visit_count = loyalty.visit_count if loyalty else 0
    tier = lounge_tier_for_visits(visit_count)

    personalization_out = None
    if personalization:
        personalization_out = lounge_personalization_to_out(personalization, guest_user)

    return LoungeMyLoyaltyOut(
        brand_id=brand_id,
        visit_count=visit_count,
        last_visit_at=loyalty.last_visit_at if loyalty else None,
        tier=tier,
        program=program_out,
        personalization=personalization_out,
    )


def record_lounge_event(
    brand_id: str,
    event_type: str,
    db: Session,
    actor_user_id: Optional[int] = None,
    guest_user_id: Optional[int] = None,
):
    db.add(
        LoungeBusinessEvent(
            brand_id=brand_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            guest_user_id=guest_user_id,
        )
    )


def build_lounge_analytics_out(brand_id: str, db: Session) -> LoungeAnalyticsOut:
    events = db.query(LoungeBusinessEvent).filter(
        LoungeBusinessEvent.brand_id == brand_id
    ).all()

    counts = defaultdict(int)
    timeline_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for event in events:
        counts[event.event_type] += 1
        day_key = event.created_at.strftime("%Y-%m-%d")
        timeline_counts[day_key][event.event_type] += 1

    loyalty_states = db.query(LoungeGuestLoyalty).filter(
        LoungeGuestLoyalty.brand_id == brand_id
    ).all()
    personalizations = db.query(LoungeGuestPersonalization).filter(
        LoungeGuestPersonalization.brand_id == brand_id
    ).all()

    today = datetime.utcnow().date()
    timeline: list[LoungeAnalyticsDayOut] = []
    for offset in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=offset)
        day_key = day.strftime("%Y-%m-%d")
        bucket = timeline_counts.get(day_key, {})
        timeline.append(
            LoungeAnalyticsDayOut(
                day_key=day_key,
                profile_views=bucket.get("profile_view", 0),
                qr_shows=bucket.get("qr_show", 0),
                qr_checkins=bucket.get("qr_checkin", 0),
                loyalty_assignments=bucket.get("loyalty_assignment", 0),
            )
        )

    # Bundle redemption stats — pack visits at this lounge
    bundle_visits = db.query(LoungeBundleVisit).filter(
        LoungeBundleVisit.brand_id == brand_id
    ).order_by(LoungeBundleVisit.visited_at.desc()).all()

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    bundle_visits_this_month_cnt = sum(
        1 for v in bundle_visits if v.visited_at >= month_start
    )

    ledger_entries = db.query(LoungeLedgerEntry).filter(
        LoungeLedgerEntry.brand_id == brand_id,
        LoungeLedgerEntry.direction == "outflow",
    ).all()
    pending_rub = sum(e.amount_rub for e in ledger_entries if e.status == "pending")
    settled_rub = sum(e.amount_rub for e in ledger_entries if e.status == "settled")

    recent_bundle_visits = []
    for v in bundle_visits[:10]:
        bundle = db.query(LoungeBundle).filter(LoungeBundle.id == v.bundle_id).first()
        recent_bundle_visits.append(BundleRecentVisitOut(
            id=v.id,
            tier=bundle.tier if bundle else "unknown",
            visited_at=v.visited_at,
            compensation_rub=v.compensation_rub,
        ))

    return LoungeAnalyticsOut(
        brand_id=brand_id,
        profile_views=counts.get("profile_view", 0),
        qr_shows=counts.get("qr_show", 0),
        qr_checkins=counts.get("qr_checkin", 0),
        loyalty_guests_count=len(loyalty_states),
        total_visits=sum(item.visit_count for item in loyalty_states),
        today_visits=sum(
            1 for item in loyalty_states
            if item.last_visit_at and item.last_visit_at.date() == today
        ),
        assigned_guests_count=len(personalizations),
        offers_count=sum(
            1 for item in personalizations
            if (item.personal_offer_title or "").strip() or (item.personal_offer_body or "").strip()
        ),
        max_assigned_discount=max(
            (item.personal_discount_percent or 0 for item in personalizations),
            default=0,
        ),
        timeline=timeline,
        bundle_visits_total=len(bundle_visits),
        bundle_visits_this_month=bundle_visits_this_month_cnt,
        bundle_compensation_pending_rub=pending_rub,
        bundle_compensation_settled_rub=settled_rub,
        bundle_recent_visits=recent_bundle_visits,
    )


def admin_user_to_out(user: User, db: Session) -> AdminUserRowOut:
    latest_mix = db.query(Mix).filter(
        Mix.author_id == user.id
    ).order_by(
        Mix.created_at.desc(),
        Mix.id.desc()
    ).first()

    mixes_count = db.query(Mix).filter(Mix.author_id == user.id).count()
    followers_count = db.query(UserFollow).filter(
        UserFollow.following_id == user.id
    ).count()
    favorites_received = db.query(Favorite).join(
        Mix, Favorite.mix_id == Mix.id
    ).filter(
        Mix.author_id == user.id
    ).count()

    return AdminUserRowOut(
        id=user.id,
        email=user.email,
        username=user.username,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
        ban_reason=user.ban_reason,
        mixes_count=mixes_count,
        followers_count=followers_count,
        favorites_received=favorites_received,
        latest_mix_name=latest_mix.name if latest_mix else None,
        latest_mix_created_at=latest_mix.created_at if latest_mix else None
    )


def admin_mix_to_out(mix: Mix, db: Session) -> AdminMixRowOut:
    likes_count = db.query(Favorite).filter(Favorite.mix_id == mix.id).count()
    comments_count = db.query(Comment).filter(Comment.mix_id == mix.id).count()
    ingredients_count = db.query(MixIngredient).filter(
        MixIngredient.mix_id == mix.id
    ).count()

    return AdminMixRowOut(
        id=mix.id,
        name=mix.name,
        author_id=mix.author_id,
        author_username=mix.author.username if mix.author else None,
        created_at=mix.created_at,
        likes_count=likes_count,
        comments_count=comments_count,
        ingredients_count=ingredients_count
    )


def delete_mix_record(mix: Mix, db: Session):
    db.query(MonthlyVote).filter(
        MonthlyVote.mix_id == mix.id
    ).delete(synchronize_session=False)
    db.query(Favorite).filter(
        Favorite.mix_id == mix.id
    ).delete(synchronize_session=False)
    db.query(Comment).filter(
        Comment.mix_id == mix.id
    ).delete(synchronize_session=False)
    db.query(MixIngredient).filter(
        MixIngredient.mix_id == mix.id
    ).delete(synchronize_session=False)
    db.delete(mix)


def delete_user_record(user: User, db: Session):
    mix_ids = [
        mix_id
        for (mix_id,) in db.query(Mix.id).filter(
            Mix.author_id == user.id
        ).all()
    ]

    if mix_ids:
        db.query(MonthlyVote).filter(
            MonthlyVote.mix_id.in_(mix_ids)
        ).delete(synchronize_session=False)
        db.query(Favorite).filter(
            Favorite.mix_id.in_(mix_ids)
        ).delete(synchronize_session=False)
        db.query(Comment).filter(
            Comment.mix_id.in_(mix_ids)
        ).delete(synchronize_session=False)
        db.query(MixIngredient).filter(
            MixIngredient.mix_id.in_(mix_ids)
        ).delete(synchronize_session=False)
        db.query(Mix).filter(
            Mix.id.in_(mix_ids)
        ).delete(synchronize_session=False)

    db.query(Favorite).filter(
        Favorite.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(Comment).filter(
        Comment.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(MonthlyVote).filter(
        MonthlyVote.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(UserFollow).filter(
        UserFollow.follower_id == user.id
    ).delete(synchronize_session=False)
    db.query(UserFollow).filter(
        UserFollow.following_id == user.id
    ).delete(synchronize_session=False)
    db.query(BowlHeatRun).filter(
        BowlHeatRun.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(UserActivity).filter(
        UserActivity.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(UserProgress).filter(
        UserProgress.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(LoungeGuestLoyalty).filter(
        LoungeGuestLoyalty.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(LoungeGuestPersonalization).filter(
        LoungeGuestPersonalization.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(LoungeGuestPersonalization).filter(
        LoungeGuestPersonalization.updated_by_user_id == user.id
    ).delete(synchronize_session=False)
    db.query(LoungeProgram).filter(
        LoungeProgram.updated_by_user_id == user.id
    ).update(
        {"updated_by_user_id": None},
        synchronize_session=False
    )
    db.query(LoungeBusinessEvent).filter(
        LoungeBusinessEvent.actor_user_id == user.id
    ).delete(synchronize_session=False)
    db.query(LoungeBusinessEvent).filter(
        LoungeBusinessEvent.guest_user_id == user.id
    ).delete(synchronize_session=False)
    db.delete(user)


def current_month_bounds() -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        next_month_start = datetime(now.year + 1, 1, 1)
    else:
        next_month_start = datetime(now.year, now.month + 1, 1)
    return month_start, next_month_start


def format_remaining_time(until: datetime) -> str:
    remaining = max(until - datetime.utcnow(), timedelta())
    days = remaining.days
    hours = remaining.seconds // 3600
    if days > 0:
        return f"{days} д. {hours} ч."
    minutes = (remaining.seconds % 3600) // 60
    return f"{hours} ч. {minutes} мин."


def vote_mix_to_out(mix: Mix, percentage: float) -> VoteMixOut:
    brands = [ingredient.brand for ingredient in mix.ingredients if ingredient.brand]
    lounge = mix.author.username if mix.author and mix.author.username else ""
    if not lounge:
        unique_brands = list(dict.fromkeys(brands))
        lounge = " · ".join(unique_brands[:2]) if unique_brands else "Hookah Lounge"

    return VoteMixOut(
        id=mix.id,
        name=mix.name,
        lounge=lounge,
        percentage=percentage,
        image_name=mix.bowl_image_name
    )


def build_monthly_flavor(db: Session) -> MonthlyFlavorOut:
    month_start, next_month_start = current_month_bounds()
    campaign = {
        "title": "Strawberry Wars",
        "subtitle": "Собери микс с клубничным профилем, попади в топ недели и продвинь бренд-партнёр в ленте.",
        "sponsor_brand": "Must Have",
        "featured_flavor": "Pinkman",
        "challenge_title": "Собери авторский микс с клубничным акцентом",
        "challenge_reward": "+30 баллов, фича в ленте и отметка партнёра месяца",
        "cta_title": "Собрать микс месяца",
    }

    mixes = db.query(Mix).options(
        joinedload(Mix.ingredients),
        joinedload(Mix.author)
    ).order_by(
        Mix.created_at.desc(),
        Mix.id.desc()
    ).all()

    monthly_votes = db.query(MonthlyVote).filter(
        MonthlyVote.created_at >= month_start,
        MonthlyVote.created_at < next_month_start
    ).all()

    vote_counts: dict[int, int] = {}
    for vote in monthly_votes:
        vote_counts[vote.mix_id] = vote_counts.get(vote.mix_id, 0) + 1

    mixes_with_stats = []
    for mix in mixes:
        likes_count = db.query(Favorite).filter(Favorite.mix_id == mix.id).count()
        mixes_with_stats.append(
            (
                mix,
                vote_counts.get(mix.id, 0),
                likes_count
            )
        )

    mixes_with_stats.sort(
        key=lambda item: (item[1], item[2], item[0].created_at or datetime.min, item[0].id),
        reverse=True
    )

    top_mixes = [item[0] for item in mixes_with_stats[:3]]
    if not top_mixes:
        return MonthlyFlavorOut(
            title=campaign["title"],
            subtitle="Появятся первые миксы и откроется голосование месяца.",
            remaining_time=format_remaining_time(next_month_start),
            progress=0.0,
            sponsor_brand=campaign["sponsor_brand"],
            featured_flavor=campaign["featured_flavor"],
            challenge_title=campaign["challenge_title"],
            challenge_reward=campaign["challenge_reward"],
            cta_title=campaign["cta_title"],
            mixes=[]
        )

    weighted_scores = []
    for mix, monthly_vote_count, likes_count in mixes_with_stats[:3]:
        score = monthly_vote_count if monthly_vote_count > 0 else max(likes_count, 0) + 1
        weighted_scores.append(score)

    total_score = max(sum(weighted_scores), 1)
    vote_mix_items = [
        vote_mix_to_out(mix, score / total_score)
        for mix, score in zip(top_mixes, weighted_scores)
    ]

    monthly_activity = min(len(monthly_votes) / 25.0, 1.0)

    return MonthlyFlavorOut(
        title=campaign["title"],
        subtitle=campaign["subtitle"],
        remaining_time=format_remaining_time(next_month_start),
        progress=monthly_activity,
        sponsor_brand=campaign["sponsor_brand"],
        featured_flavor=campaign["featured_flavor"],
        challenge_title=campaign["challenge_title"],
        challenge_reward=campaign["challenge_reward"],
        cta_title=campaign["cta_title"],
        mixes=vote_mix_items
    )

# -------------------------------------------------------------------
# APP
# -------------------------------------------------------------------
app = FastAPI(title="HookahMix API")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        # MARK: lounge_assets — created by create_all if new DB, or via ALTER for existing prod
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS lounge_assets (
                id SERIAL PRIMARY KEY,
                brand_id VARCHAR UNIQUE NOT NULL,
                avatar_url TEXT,
                cover_url TEXT,
                photo_urls TEXT DEFAULT '[]',
                info_json TEXT DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_lounge_assets_brand_id ON lounge_assets (brand_id)
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS ban_reason TEXT
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS banned_at TIMESTAMP
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE users
            SET is_admin = FALSE
            WHERE is_admin IS NULL
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE users
            SET is_banned = FALSE
            WHERE is_banned IS NULL
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE mixes
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE mixes
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE comments
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE comments
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO user_progress (user_id, points, rating, streak_days, created_at, updated_at)
            SELECT users.id, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM users
            WHERE NOT EXISTS (
                SELECT 1
                FROM user_progress
                WHERE user_progress.user_id = users.id
            )
            """
        )
    db = SessionLocal()
    try:
        sync_admin_allowlist(db)
    finally:
        db.close()

# -------------------------------------------------------------------
# AUTH
# -------------------------------------------------------------------
@app.post("/signup", response_model=LoginResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_admin=False
    )
    if user_matches_admin_allowlist(user):
        user.is_admin = True
    db.add(user)
    db.flush()
    track_daily_login(user, db)
    db.commit()
    db.refresh(user)

    return LoginResponse(
        user_id=user.id,
        token=create_access_token({"sub": str(user.id)}),
        username=user.username
    )


@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User)\
        .filter(User.email == payload.email)\
        .first()

    if not user or not verify_password(
        payload.password,
        user.password_hash
    ):
        raise HTTPException(400, "Invalid credentials")

    if user.is_banned:
        raise HTTPException(403, user.ban_reason or "Account banned")

    track_daily_login(user, db)
    db.commit()

    return LoginResponse(
        user_id=user.id,
        token=create_access_token({"sub": str(user.id)}),
        username=user.username
    )

# -------------------------------------------------------------------
# PROFILE
# -------------------------------------------------------------------
@app.get("/me", response_model=UserOut)
def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")
    track_daily_login(user, db)
    db.commit()
    db.refresh(user)
    return user_to_out(user, user, db)


@app.get("/users/search", response_model=List[UserSearchOut])
def search_users(
    query: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    normalized_query = query.strip()
    if not normalized_query:
        return []

    users = db.query(User).filter(
        User.is_banned.is_(False),
        User.id != current_user.id,
        (
            User.username.ilike(f"%{normalized_query}%")
            | User.email.ilike(f"%{normalized_query}%")
        )
    ).order_by(
        User.username.asc(),
        User.id.asc()
    ).limit(12).all()

    return [user_search_to_out(item) for item in users if item.username]


@app.get("/lounges/{brand_id}/program", response_model=LoungeProgramOut)
def get_lounge_program_endpoint(
    brand_id: str,
    db: Session = Depends(get_db),
):
    return lounge_program_to_out(get_lounge_program(brand_id, db), brand_id)


@app.put("/lounges/{brand_id}/program", response_model=LoungeProgramOut)
def update_lounge_program(
    brand_id: str,
    payload: LoungeProgramIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    program = get_lounge_program(brand_id, db)
    if not program:
        program = LoungeProgram(brand_id=brand_id)
        db.add(program)

    program.title = payload.title.strip()
    program.summary = payload.summary.strip()
    program.base_discount_percent = max(min(payload.base_discount_percent, 50), 0)
    program.welcome_offer_title = payload.welcome_offer_title.strip()
    program.welcome_offer_body = payload.welcome_offer_body.strip()
    program.updated_by_user_id = current_user.id
    program.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(program)
    return lounge_program_to_out(program, brand_id)


# -------------------------------------------------------------------
# LOUNGE ASSETS  (avatar / cover / gallery / info)
# -------------------------------------------------------------------

def _parse_lounge_assets(assets: Optional[LoungeAssets], brand_id: str) -> LoungeAssetsOut:
    """Convert DB row → response DTO. Handles missing row gracefully."""
    import json as _json
    if assets is None:
        return LoungeAssetsOut(brand_id=brand_id)
    try:
        photos = _json.loads(assets.photo_urls or "[]")
        if not isinstance(photos, list):
            photos = []
    except Exception:
        photos = []
    try:
        info = _json.loads(assets.info_json or "{}")
        if not isinstance(info, dict):
            info = {}
    except Exception:
        info = {}
    return LoungeAssetsOut(
        brand_id=brand_id,
        avatar_url=assets.avatar_url,
        cover_url=assets.cover_url,
        photos=photos,
        info=info,
        updated_at=assets.updated_at,
    )


@app.get("/lounges/{brand_id}/assets", response_model=LoungeAssetsOut)
def get_lounge_assets(
    brand_id: str,
    db: Session = Depends(get_db),
):
    """
    Public endpoint — returns stored avatar, cover, gallery and info for a lounge.
    No auth required: iOS uses this to display venue card without parsing.
    """
    assets = db.query(LoungeAssets).filter(LoungeAssets.brand_id == brand_id).first()
    return _parse_lounge_assets(assets, brand_id)


@app.put("/lounges/{brand_id}/assets", response_model=LoungeAssetsOut)
def update_lounge_assets(
    brand_id: str,
    payload: LoungeAssetsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Manager-only endpoint — set / update avatar, cover, gallery photos and info JSON.
    Partial update: omit a field to keep existing value.
    """
    import json as _json
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    assets = db.query(LoungeAssets).filter(LoungeAssets.brand_id == brand_id).first()
    if assets is None:
        assets = LoungeAssets(brand_id=brand_id, photo_urls="[]", info_json="{}")
        db.add(assets)

    if payload.avatar_url is not None:
        assets.avatar_url = payload.avatar_url.strip() or None
    if payload.cover_url is not None:
        assets.cover_url = payload.cover_url.strip() or None
    if payload.photos is not None:
        # Validate: list of non-empty strings, max 20
        clean = [u.strip() for u in payload.photos if isinstance(u, str) and u.strip()][:20]
        assets.photo_urls = _json.dumps(clean, ensure_ascii=False)
    if payload.info is not None:
        assets.info_json = _json.dumps(payload.info, ensure_ascii=False)

    assets.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assets)
    return _parse_lounge_assets(assets, brand_id)


@app.get("/lounges/{brand_id}/my-loyalty", response_model=LoungeMyLoyaltyOut)
def get_my_lounge_loyalty(
    brand_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    return build_lounge_loyalty_out(brand_id, current_user, db)


@app.get("/lounges/{brand_id}/guests", response_model=List[LoungeGuestRecordOut])
def list_lounge_guest_records(
    brand_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    rows = db.query(LoungeGuestPersonalization, User).join(
        User, User.id == LoungeGuestPersonalization.user_id
    ).filter(
        LoungeGuestPersonalization.brand_id == brand_id
    ).order_by(
        LoungeGuestPersonalization.updated_at.desc(),
        LoungeGuestPersonalization.id.desc()
    ).all()

    return [lounge_personalization_to_out(record, guest_user) for record, guest_user in rows]


@app.post("/lounges/{brand_id}/guests", response_model=LoungeGuestRecordOut)
def upsert_lounge_guest_record(
    brand_id: str,
    payload: LoungeGuestRecordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    guest_user = None
    if payload.user_id is not None:
        guest_user = db.query(User).filter(User.id == payload.user_id).first()
    if guest_user is None and payload.username:
        guest_user = db.query(User).filter(
            func.lower(User.username) == payload.username.strip().replace("@", "").lower()
        ).first()
    if guest_user is None:
        raise HTTPException(404, "User not found")

    record = db.query(LoungeGuestPersonalization).filter(
        LoungeGuestPersonalization.brand_id == brand_id,
        LoungeGuestPersonalization.user_id == guest_user.id,
    ).first()
    if not record:
        record = LoungeGuestPersonalization(
            brand_id=brand_id,
            user_id=guest_user.id,
        )
        db.add(record)

    record.display_name = (payload.display_name or "").strip() or guest_user.username
    record.favorite_order = (payload.favorite_order or "").strip() or None
    record.average_check = payload.average_check
    record.visit_count = max(payload.visit_count, 0)
    record.personal_tier_title = (payload.personal_tier_title or "").strip() or None
    record.personal_discount_percent = payload.personal_discount_percent
    record.personal_offer_title = (payload.personal_offer_title or "").strip() or None
    record.personal_offer_body = (payload.personal_offer_body or "").strip() or None
    record.note = (payload.note or "").strip() or None
    record.updated_by_user_id = current_user.id
    record.updated_at = datetime.utcnow()

    record_lounge_event(
        brand_id,
        "loyalty_assignment",
        db,
        actor_user_id=current_user.id,
        guest_user_id=guest_user.id,
    )

    db.commit()
    db.refresh(record)
    return lounge_personalization_to_out(record, guest_user)


@app.delete("/lounges/{brand_id}/guests/{guest_user_id}", response_model=StatusOut)
def delete_lounge_guest_record(
    brand_id: str,
    guest_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    db.query(LoungeGuestPersonalization).filter(
        LoungeGuestPersonalization.brand_id == brand_id,
        LoungeGuestPersonalization.user_id == guest_user_id,
    ).delete(synchronize_session=False)
    db.commit()
    return StatusOut(status="ok", message="Guest loyalty record removed")


@app.post("/lounges/{brand_id}/checkin", response_model=LoungeCheckinOut)
def register_lounge_checkin(
    brand_id: str,
    payload: LoungeCheckinIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    guest_user = None
    if payload.user_id is not None:
        guest_user = db.query(User).filter(User.id == payload.user_id).first()
    if guest_user is None and payload.username:
        guest_user = db.query(User).filter(
            func.lower(User.username) == payload.username.strip().replace("@", "").lower()
        ).first()
    if guest_user is None or not guest_user.username:
        raise HTTPException(404, "Guest user not found")

    loyalty = db.query(LoungeGuestLoyalty).filter(
        LoungeGuestLoyalty.brand_id == brand_id,
        LoungeGuestLoyalty.user_id == guest_user.id,
    ).first()
    if not loyalty:
        loyalty = LoungeGuestLoyalty(
            brand_id=brand_id,
            user_id=guest_user.id,
            visit_count=0,
        )
        db.add(loyalty)
        db.flush()

    today = datetime.utcnow().date()
    # Unlimited visits for dorfden (user_id=1)
    is_unlimited_user = (guest_user.id == 1)
    if loyalty.last_visit_at and loyalty.last_visit_at.date() == today and not is_unlimited_user:
        cnt = loyalty.today_visit_count or 0
        if cnt >= 3:
            raise HTTPException(400, "Visit already registered today")
        loyalty.today_visit_count = cnt + 1
    else:
        loyalty.today_visit_count = (loyalty.today_visit_count or 0) + 1 if (loyalty.last_visit_at and loyalty.last_visit_at.date() == today) else 1

    previous_tier = lounge_tier_for_visits(loyalty.visit_count)
    loyalty.visit_count += 1
    loyalty.last_visit_at = datetime.utcnow()

    personalization = db.query(LoungeGuestPersonalization).filter(
        LoungeGuestPersonalization.brand_id == brand_id,
        LoungeGuestPersonalization.user_id == guest_user.id,
    ).first()
    program = get_lounge_program(brand_id, db)
    program_out = lounge_program_to_out(program, brand_id)
    if not personalization:
        personalization = LoungeGuestPersonalization(
            brand_id=brand_id,
            user_id=guest_user.id,
            display_name=(payload.display_name or guest_user.username),
            visit_count=loyalty.visit_count,
            personal_discount_percent=program_out.base_discount_percent,
            updated_by_user_id=current_user.id,
            updated_at=datetime.utcnow(),
        )
        db.add(personalization)
    else:
        personalization.visit_count = max(personalization.visit_count, loyalty.visit_count)
        personalization.updated_by_user_id = current_user.id
        personalization.updated_at = datetime.utcnow()

    record_lounge_event(
        brand_id,
        "qr_checkin",
        db,
        actor_user_id=current_user.id,
        guest_user_id=guest_user.id,
    )

    db.commit()

    loyalty_out = build_lounge_loyalty_out(brand_id, guest_user, db)
    is_level_up = previous_tier.title != loyalty_out.tier.title
    message = (
        f"Визит @{guest_user.username} в {display_title_from_brand_id(brand_id)} засчитан: "
        f"{loyalty_out.tier.title}, {loyalty_out.tier.discount_text} скидки."
    )

    # Bundle redemption — burn one included hookah if guest has active pack
    bundle_redeemed_out = _try_redeem_bundle_visit(db, guest_user.id, brand_id)


    # Create pending duel offer for guest
    from sqlalchemy import text as _sa_text
    db.execute(_sa_text("INSERT INTO pending_duel_offers (user_id, brand_id, discount_percent) VALUES (:uid, :bid, :disc)"), {"uid": guest_user.id, "bid": brand_id, "disc": loyalty_out.tier.discount_percent})
    db.commit()
    return LoungeCheckinOut(
        guest=user_search_to_out(guest_user),
        loyalty=loyalty_out,
        is_level_up=is_level_up,
        message=message,
        bundle_redeemed=bundle_redeemed_out,
    )


def _try_redeem_bundle_visit(db: Session, guest_user_id: int, brand_id: str):
    """Find active bundle of the guest, burn one hookah if available, queue
    a pending payout to the lounge via ledger. Returns BundleRedemptionOut
    or None."""
    now = datetime.utcnow()
    bundle = db.query(LoungeBundle).filter(
        LoungeBundle.user_id == guest_user_id,
        LoungeBundle.status == "active",
        LoungeBundle.expires_at > now,
    ).order_by(LoungeBundle.started_at.asc()).first()
    if not bundle:
        return None

    # Check remaining hookahs (0 means unlimited for cityPass)
    used = db.query(LoungeBundleVisit).filter(
        LoungeBundleVisit.bundle_id == bundle.id
    ).count()
    if bundle.max_visits > 0 and used >= bundle.max_visits:
        # Pack exhausted — mark as expired so next lookups are cheap
        bundle.status = "expired"
        db.flush()
        return None

    visit = LoungeBundleVisit(
        bundle_id=bundle.id,
        user_id=guest_user_id,
        brand_id=brand_id,
        compensation_rub=bundle.compensation_per_visit_rub,
        visited_at=now,
    )
    db.add(visit)
    db.flush()

    db.add(LoungeLedgerEntry(
        brand_id=brand_id,
        user_id=guest_user_id,
        bundle_id=bundle.id,
        bundle_visit_id=visit.id,
        direction="outflow",
        amount_rub=bundle.compensation_per_visit_rub,
        status="pending",
        description=f"Bundle visit — {bundle.tier} @ {brand_id}",
        created_at=now,
    ))

    remaining = None if bundle.max_visits == 0 else max(0, bundle.max_visits - (used + 1))
    return BundleRedemptionOut(
        bundle_id=bundle.id,
        tier=bundle.tier,
        hookah_number=used + 1,
        remaining=remaining,
        compensation_rub=bundle.compensation_per_visit_rub,
    )


@app.get("/lounges/{brand_id}/analytics", response_model=LoungeAnalyticsOut)
def get_lounge_analytics(
    brand_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")
    return build_lounge_analytics_out(brand_id, db)


@app.post("/lounges/{brand_id}/events/profile-view", response_model=StatusOut)
def track_lounge_profile_view(
    brand_id: str,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    record_lounge_event(
        brand_id,
        "profile_view",
        db,
        actor_user_id=user.id if user else None,
    )
    db.commit()
    return StatusOut(status="ok")


@app.post("/lounges/{brand_id}/events/qr-show", response_model=StatusOut)
def track_lounge_qr_show(
    brand_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    record_lounge_event(
        brand_id,
        "qr_show",
        db,
        actor_user_id=current_user.id,
    )
    db.commit()
    return StatusOut(status="ok")


@app.get("/mini-game/heat-bowl", response_model=BowlHeatGameStateOut)
def get_bowl_heat_state(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")
    return build_bowl_heat_state(user, db)


@app.post("/mini-game/heat-bowl/play", response_model=BowlHeatPlayOut)
def play_bowl_heat(
    payload: BowlHeatPlayIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    state_before = build_bowl_heat_state(user, db)
    if not state_before.can_play:
        raise HTTPException(400, "Daily attempts exhausted")

    score = max(min(payload.score, 100), 0)
    duration_seconds = max(min(payload.duration_seconds, float(BOWL_HEAT_DURATION_SECONDS)), 1.0)
    sweet_spot_seconds = max(min(payload.sweet_spot_seconds, duration_seconds), 0.0)
    overheat_seconds = max(min(payload.overheat_seconds, duration_seconds), 0.0)
    taps_count = max(payload.taps_count, 0)

    previous_best_reward = (
        bowl_heat_reward_for_score(state_before.best_score_today)
        if state_before.best_score_today > 0
        else {"points": 0, "rating": 0}
    )
    current_reward = bowl_heat_reward_for_score(score)
    is_new_best = score > state_before.best_score_today

    points_awarded = 0
    rating_awarded = 0
    if is_new_best:
        points_awarded = max(current_reward["points"] - previous_best_reward["points"], 0)
        rating_awarded = max(current_reward["rating"] - previous_best_reward["rating"], 0)

    run = BowlHeatRun(
        user_id=user.id,
        score=score,
        sweet_spot_seconds=round(sweet_spot_seconds, 2),
        overheat_seconds=round(overheat_seconds, 2),
        taps_count=taps_count,
        duration_seconds=round(duration_seconds, 2),
        reward_points=points_awarded,
        reward_rating=rating_awarded,
        tier_title=current_reward["tier"]
    )
    db.add(run)

    if points_awarded > 0 or rating_awarded > 0:
        record_progress_event(
            user=user,
            db=db,
            event_type="bowl_heat_best",
            title=current_reward["title"],
            description=f"Лучшая попытка дня: {score}/100 · жара в зоне {round(sweet_spot_seconds, 1)} с.",
            points_delta=points_awarded,
            rating_delta=rating_awarded
        )

    db.commit()
    state_after = build_bowl_heat_state(user, db)

    return BowlHeatPlayOut(
        score=score,
        tier=current_reward["tier"],
        result_title=current_reward["title"],
        result_message=current_reward["message"],
        points_awarded=points_awarded,
        rating_awarded=rating_awarded,
        is_new_best=is_new_best,
        state=state_after
    )


@app.get("/monthly", response_model=MonthlyFlavorOut)
@app.post("/monthly", response_model=MonthlyFlavorOut)
def get_monthly_flavor(db: Session = Depends(get_db)):
    return build_monthly_flavor(db)


@app.post("/mixes/{mix_id}/vote", response_model=VoteMixOut)
def vote_for_mix(
    mix_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    mix = db.query(Mix).options(
        joinedload(Mix.ingredients),
        joinedload(Mix.author)
    ).get(mix_id)
    if not mix:
        raise HTTPException(404, "Mix not found")

    month_start, next_month_start = current_month_bounds()
    db.query(MonthlyVote).filter(
        MonthlyVote.user_id == user.id,
        MonthlyVote.created_at >= month_start,
        MonthlyVote.created_at < next_month_start
    ).delete()

    db.add(MonthlyVote(user_id=user.id, mix_id=mix_id))
    db.commit()

    monthly = build_monthly_flavor(db)
    for candidate in monthly.mixes:
        if candidate.id == mix_id:
            return candidate

    return vote_mix_to_out(mix, 0.0)


@app.get("/mixes/following", response_model=List[MixOut])
def list_following_mixes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    followed_ids = [
        row.following_id
        for row in db.query(UserFollow).filter(
            UserFollow.follower_id == user.id
        ).all()
    ]

    if not followed_ids:
        return []

    mixes = db.query(Mix).options(
        joinedload(Mix.ingredients),
        joinedload(Mix.author)
    ).filter(
        Mix.author_id.in_(followed_ids)
    ).order_by(
        Mix.created_at.desc(),
        Mix.id.desc()
    ).all()
    return [mix_to_out(m, user, db) for m in mixes]


@app.get("/mixes", response_model=List[MixOut])
def list_mixes(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    mixes = db.query(Mix).options(
        joinedload(Mix.ingredients),
        joinedload(Mix.author)
    ).order_by(Mix.created_at.desc(), Mix.id.desc()).all()
    return [mix_to_out(m, user, db) for m in mixes]


@app.get("/mixes/{mix_id}", response_model=MixOut)
def get_mix(
    mix_id: int,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    mix = db.query(Mix).options(
        joinedload(Mix.ingredients),
        joinedload(Mix.author)
    ).get(mix_id)
    if not mix:
        raise HTTPException(404, "Mix not found")
    return mix_to_out(mix, user, db)


@app.post("/mixes", response_model=MixOut)
def create_mix(
    payload: MixCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    mix_slots_state = mix_slots_state_for_user(user, db)
    max_mix_slots = mix_slots_state["max_mix_slots"]
    mixes_used = mix_slots_state["mixes_used"]
    next_threshold = mix_slots_state["next_threshold"]

    if max_mix_slots is not None and mixes_used >= max_mix_slots:
        if next_threshold is not None:
            next_slots = mix_slots_for_rating(next_threshold)
            detail = (
                f"На твоём уровне доступно только {max_mix_slots} "
                f"{russian_mix_word(max_mix_slots)}. "
                f"Сейчас все слоты заняты. Чтобы открыть {next_slots} "
                f"{russian_mix_word(next_slots)}, подними рейтинг до {next_threshold}. "
                "Лайки, сохранения и комментарии к твоим миксам повышают уровень. "
                "Либо освободи слот, удалив один из старых миксов."
            )
        else:
            detail = (
                f"На твоём уровне доступно только {max_mix_slots} "
                f"{russian_mix_word(max_mix_slots)}. "
                "Сейчас все слоты заняты. Освободи слот, удалив один из старых миксов."
            )
        raise HTTPException(403, detail)

    mix = Mix(
        author_id=user.id,
        **payload.dict(exclude={"ingredients"})
    )
    db.add(mix)
    db.flush()

    for ing in payload.ingredients:
        db.add(MixIngredient(
            mix_id=mix.id,
            brand=ing.brand,
            flavor=ing.flavor,
            percentage=ing.percentage
        ))

    award_event(
        user,
        "mix_created",
        db,
        description=f"Опубликован микс «{mix.name}»"
    )
    db.commit()
    db.refresh(mix)
    return mix_to_out(mix, user, db)
@app.post("/mixes/{mix_id}/comments", response_model=CommentOut)
def add_comment(
    mix_id: int,
    payload: CommentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    mix = db.query(Mix).get(mix_id)
    if not mix:
        raise HTTPException(404, "Mix not found")

    comment = Comment(
        mix_id=mix_id,
        user_id=user.id,
        text=payload.text
    )
    db.add(comment)
    award_event(
        user,
        "comment_created",
        db,
        description=f"Комментарий к миксу «{mix.name}»"
    )
    if mix.author_id and mix.author_id != user.id:
        mix_author = db.query(User).get(mix.author_id)
        award_event(
            mix_author,
            "comment_received",
            db,
            description=f"Новый комментарий к миксу «{mix.name}»"
        )
    db.commit()
    db.refresh(comment)
    comment = db.query(Comment).options(
        joinedload(Comment.user)
    ).filter(Comment.id == comment.id).first()
    return comment_to_out(comment)


@app.get("/mixes/{mix_id}/comments", response_model=List[CommentOut])
def list_comments(mix_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).options(
        joinedload(Comment.user)
    )\
        .filter(Comment.mix_id == mix_id)\
        .order_by(Comment.created_at.desc(), Comment.id.desc())\
        .all()
    return [comment_to_out(comment) for comment in comments]
@app.get("/users/{user_id}", response_model=UserOut)
def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
    viewer: Optional[User] = Depends(get_current_user)
):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    return user_to_out(user, viewer, db)
@app.put("/mixes/{mix_id}", response_model=MixOut)
def update_mix(
    mix_id: int,
    payload: MixCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    mix = db.query(Mix).get(mix_id)
    if not mix:
        raise HTTPException(404, "Mix not found")

    if mix.author_id != user.id:
        raise HTTPException(403, "Forbidden")

    for field, value in payload.dict(exclude={"ingredients"}).items():
        setattr(mix, field, value)

    db.query(MixIngredient).filter(
        MixIngredient.mix_id == mix.id
    ).delete()

    for ing in payload.ingredients:
        db.add(MixIngredient(
            mix_id=mix.id,
            brand=ing.brand,
            flavor=ing.flavor,
            percentage=ing.percentage
        ))

    db.commit()
    db.refresh(mix)
    return mix_to_out(mix, user, db)
@app.delete("/mixes/{mix_id}")
def delete_mix(
    mix_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    mix = db.query(Mix).get(mix_id)
    if not mix:
        raise HTTPException(404, "Mix not found")

    if mix.author_id != user.id:
        raise HTTPException(403, "Forbidden")

    delete_mix_record(mix, db)
    db.commit()
    return {"status": "deleted"}
@app.post("/mixes/{mix_id}/favorite")
def toggle_favorite(
    mix_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    mix = db.query(Mix).options(
        joinedload(Mix.author)
    ).get(mix_id)
    if not mix:
        raise HTTPException(404, "Mix not found")

    fav = db.query(Favorite).filter_by(
        user_id=user.id,
        mix_id=mix_id
    ).first()

    if fav:
        db.delete(fav)
        is_liked = False
    else:
        db.add(Favorite(user_id=user.id, mix_id=mix_id))
        is_liked = True
        if mix.author_id and mix.author_id != user.id:
            award_event(
                mix.author,
                "mix_favorited",
                db,
                description=f"Микс «{mix.name}» добавили в избранное"
            )

    db.commit()

    likes_count = db.query(Favorite)\
        .filter(Favorite.mix_id == mix_id)\
        .count()

    return {
        "is_liked": is_liked,
        "likes_count": likes_count
    }
@app.get("/users/{user_id}/likes", response_model=List[MixOut])
def liked_mixes(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user)
):
    if not current or current.id != user_id:
        raise HTTPException(403, "Forbidden")

    favs = db.query(Favorite).options(
        joinedload(Favorite.mix).joinedload(Mix.ingredients),
        joinedload(Favorite.mix).joinedload(Mix.author)
    ).filter(
        Favorite.user_id == user_id
    ).all()

    mixes = [f.mix for f in favs]
    return [mix_to_out(m, current, db) for m in mixes]


@app.post("/users/{user_id}/follow", response_model=FollowToggleOut)
def toggle_follow_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user)
):
    if not current:
        raise HTTPException(401, "Unauthorized")
    if current.id == user_id:
        raise HTTPException(400, "Cannot follow yourself")

    target_user = db.query(User).get(user_id)
    if not target_user:
        raise HTTPException(404, "User not found")

    follow = db.query(UserFollow).filter_by(
        follower_id=current.id,
        following_id=user_id
    ).first()

    if follow:
        db.delete(follow)
        is_following = False
    else:
        db.add(UserFollow(
            follower_id=current.id,
            following_id=user_id
        ))
        is_following = True

    db.commit()
    return FollowToggleOut(user_id=user_id, is_following=is_following)


@app.get("/favorites", response_model=List[MixOut])
def get_favorites(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user)
):
    if not current:
        raise HTTPException(401, "Unauthorized")

    favs = db.query(Favorite).options(
        joinedload(Favorite.mix).joinedload(Mix.ingredients),
        joinedload(Favorite.mix).joinedload(Mix.author)
    ).filter(
        Favorite.user_id == current.id
    ).order_by(Favorite.id.desc()).all()

    mixes = [f.mix for f in favs if f.mix is not None]
    return [mix_to_out(m, current, db) for m in mixes]


@app.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    comment = db.query(Comment).get(comment_id)
    if not comment:
        raise HTTPException(404, "Comment not found")

    if comment.user_id != user.id:
        raise HTTPException(403, "Forbidden")

    db.delete(comment)
    db.commit()
    return {"status": "deleted"}
@app.put("/users/{user_id}")
def edit_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user)
):
    if not current or current.id != user_id:
        raise HTTPException(403, "Forbidden")

    user = db.query(User).get(user_id)

    for field, value in payload.dict().items():
        if value is not None:
            setattr(user, field, value)

    db.commit()
    return {"status": "updated"}


@app.get("/admin/dashboard", response_model=AdminDashboardOut)
def get_admin_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    users = db.query(User).order_by(User.id.desc()).all()
    recent_mixes = db.query(Mix).options(
        joinedload(Mix.author)
    ).order_by(
        Mix.created_at.desc(),
        Mix.id.desc()
    ).limit(40).all()

    stats = AdminDashboardStatsOut(
        total_users=db.query(User).count(),
        banned_users=db.query(User).filter(User.is_banned.is_(True)).count(),
        total_mixes=db.query(Mix).count(),
        total_comments=db.query(Comment).count(),
        total_favorites=db.query(Favorite).count()
    )

    return AdminDashboardOut(
        stats=stats,
        users=[admin_user_to_out(user, db) for user in users],
        recent_mixes=[admin_mix_to_out(mix, db) for mix in recent_mixes]
    )


@app.post("/admin/users/{user_id}/ban", response_model=AdminUserRowOut)
def admin_ban_user(
    user_id: int,
    payload: AdminBanIn,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    if admin.id == user_id:
        raise HTTPException(400, "Cannot ban yourself")

    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.is_banned = True
    user.ban_reason = payload.reason.strip() if payload.reason else "Нарушение правил платформы"
    user.banned_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return admin_user_to_out(user, db)


@app.post("/admin/users/{user_id}/unban", response_model=AdminUserRowOut)
def admin_unban_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    user.is_banned = False
    user.ban_reason = None
    user.banned_at = None
    db.commit()
    db.refresh(user)
    return admin_user_to_out(user, db)


@app.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    if admin.id == user_id:
        raise HTTPException(400, "Cannot delete yourself")

    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    delete_user_record(user, db)
    db.commit()
    return {"status": "deleted"}


@app.delete("/admin/mixes/{mix_id}")
def admin_delete_mix(
    mix_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    mix = db.query(Mix).get(mix_id)
    if not mix:
        raise HTTPException(404, "Mix not found")

    delete_mix_record(mix, db)
    db.commit()
    return {"status": "deleted"}
@app.get("/mixes/filter", response_model=List[MixOut])
def filter_mixes(
    mood: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends( )
):
    query = db.query(Mix)

    if mood:
        query = query.filter(Mix.mood == mood)

    mixes = query.all()
    return [mix_to_out(m, user, db) for m in mixes]


# ===============================================================
# BUNDLE SUBSCRIPTIONS — YooKassa payments + ledger
# ===============================================================

# YooKassa SDK init. Library reads Configuration.account_id / secret_key
# at send time, so we set them once at import. If env vars are missing
# endpoints return 503 — we never want to silently fall back to a
# wrong shop.
try:
    from yookassa import Configuration as YooKassaConfig, Payment as YooKassaPayment
    if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
        YooKassaConfig.account_id = YOOKASSA_SHOP_ID
        YooKassaConfig.secret_key = YOOKASSA_SECRET_KEY
        _YOOKASSA_ENABLED = True
    else:
        _YOOKASSA_ENABLED = False
except ImportError:
    _YOOKASSA_ENABLED = False


def _require_yookassa():
    if not _YOOKASSA_ENABLED:
        raise HTTPException(503, "YooKassa is not configured on the server")


def bundle_to_out(bundle: LoungeBundle) -> BundleOut:
    return BundleOut(
        id=bundle.id,
        tier=bundle.tier,
        price_rub=bundle.price_rub,
        compensation_per_visit_rub=bundle.compensation_per_visit_rub,
        max_visits=bundle.max_visits,
        started_at=bundle.started_at,
        expires_at=bundle.expires_at,
        status=bundle.status,
        visits=[
            BundleVisitOut(
                id=v.id,
                brand_id=v.brand_id,
                visited_at=v.visited_at,
                compensation_rub=v.compensation_rub,
            )
            for v in bundle.visits
        ],
    )


def _expire_stale_bundles(db: Session, user_id: int):
    """Mark bundles as 'expired' once they pass the term. Keeps 'active'
    accurate so queries don't need datetime filters in every callsite."""
    now = datetime.utcnow()
    stale = db.query(LoungeBundle).filter(
        LoungeBundle.user_id == user_id,
        LoungeBundle.status == "active",
        LoungeBundle.expires_at < now,
    ).all()
    for b in stale:
        b.status = "expired"


@app.post("/bundles/payments/create", response_model=BundlePaymentCreateOut)
def create_bundle_payment(
    payload: BundlePaymentCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Kick off a YooKassa payment for a bundle tier. Returns the
    confirmation URL the iOS client opens in a WebView.
    The bundle record is NOT created yet — we wait for the payment
    status to flip to 'succeeded' (either via polling or webhook)
    before calling /bundles/purchase to finalise."""
    _require_yookassa()
    current_user = get_required_user(user)

    tier_cfg = BUNDLE_TIERS.get(payload.tier)
    if not tier_cfg:
        raise HTTPException(400, f"Unknown tier: {payload.tier}")

    amount_rub = tier_cfg["price_rub"]
    idempotence_key = f"bundle-{current_user.id}-{payload.tier}-{int(datetime.utcnow().timestamp())}"

    try:
        yp = YooKassaPayment.create({
            "amount": {
                "value": f"{amount_rub:.2f}",
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": YOOKASSA_RETURN_URL,
            },
            "capture": True,
            "description": f"{tier_cfg['title']} — Hooka3",
            "metadata": {
                "user_id": str(current_user.id),
                "tier": payload.tier,
                "source": "ios_app",
            },
        }, idempotence_key)
    except Exception as exc:
        raise HTTPException(502, f"YooKassa error: {exc}")

    return BundlePaymentCreateOut(
        payment_id=yp.id,
        confirmation_url=yp.confirmation.confirmation_url,
        amount_rub=amount_rub,
    )


@app.get("/bundles/payments/{payment_id}/status", response_model=BundlePaymentStatusOut)
def get_bundle_payment_status(
    payment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Polled by the iOS client after the WebView closes. If paid,
    the client calls /bundles/purchase to finalise — the status
    endpoint itself is idempotent and does NOT create bundles."""
    _require_yookassa()
    current_user = get_required_user(user)

    try:
        yp = YooKassaPayment.find_one(payment_id)
    except Exception as exc:
        raise HTTPException(502, f"YooKassa error: {exc}")

    meta_user_id = (yp.metadata or {}).get("user_id") if yp else None
    if meta_user_id and str(current_user.id) != str(meta_user_id):
        raise HTTPException(403, "Payment belongs to a different user")

    existing = db.query(LoungeBundle).filter(
        LoungeBundle.user_id == current_user.id,
        LoungeBundle.purchase_receipt_id == payment_id,
    ).first()

    return BundlePaymentStatusOut(
        payment_id=payment_id,
        status=yp.status,
        paid=bool(yp.paid),
        bundle_id=existing.id if existing else None,
    )


@app.post("/bundles/purchase", response_model=BundleOut)
def finalise_bundle_purchase(
    payload: BundlePaymentCreateOut,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Finalise a bundle after YooKassa reports succeeded.
    Idempotent: if a bundle already exists for this payment_id it is
    returned as-is.
    Reuses BundlePaymentCreateOut as input since we only need
    payment_id + tier — lightweight and matches what the client has."""
    _require_yookassa()
    current_user = get_required_user(user)

    # Idempotency
    existing = db.query(LoungeBundle).filter(
        LoungeBundle.user_id == current_user.id,
        LoungeBundle.purchase_receipt_id == payload.payment_id,
    ).first()
    if existing:
        return bundle_to_out(existing)

    # Verify payment succeeded on YooKassa side — never trust the client
    try:
        yp = YooKassaPayment.find_one(payload.payment_id)
    except Exception as exc:
        raise HTTPException(502, f"YooKassa error: {exc}")
    if not yp.paid or yp.status != "succeeded":
        raise HTTPException(400, f"Payment is not succeeded (status={yp.status})")

    meta = yp.metadata or {}
    meta_user_id = meta.get("user_id")
    if meta_user_id and str(current_user.id) != str(meta_user_id):
        raise HTTPException(403, "Payment belongs to a different user")

    tier = meta.get("tier")
    tier_cfg = BUNDLE_TIERS.get(tier)
    if not tier_cfg:
        raise HTTPException(400, f"Unknown tier in payment metadata: {tier}")

    now = datetime.utcnow()
    bundle = LoungeBundle(
        user_id=current_user.id,
        tier=tier,
        lounge_ids="",  # legacy column, not used in the "any partner" model
        discount_percent=0,
        max_visits=(tier_cfg["hookahs"] or 0),
        compensation_per_visit_rub=tier_cfg["comp_rub"],
        price_rub=tier_cfg["price_rub"],
        purchase_provider="yookassa",
        purchase_receipt_id=payload.payment_id,
        started_at=now,
        expires_at=now + timedelta(days=tier_cfg["days"]),
        status="active",
    )
    db.add(bundle)
    db.flush()

    # Inflow entry — user paid us
    db.add(LoungeLedgerEntry(
        brand_id=None,
        user_id=current_user.id,
        bundle_id=bundle.id,
        direction="inflow",
        amount_rub=tier_cfg["price_rub"],
        status="settled",  # money hit our YooKassa account already
        description=f"Bundle sale — {tier_cfg['title']}",
        settled_at=now,
    ))

    db.commit()
    db.refresh(bundle)
    return bundle_to_out(bundle)


@app.get("/users/me/bundles", response_model=BundleListOut)
def list_my_bundles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    _expire_stale_bundles(db, current_user.id)
    db.commit()

    all_bundles = db.query(LoungeBundle).filter(
        LoungeBundle.user_id == current_user.id,
    ).order_by(LoungeBundle.started_at.desc()).all()

    active = [b for b in all_bundles if b.status == "active"]
    past = [b for b in all_bundles if b.status != "active"]
    return BundleListOut(
        active=[bundle_to_out(b) for b in active],
        past=[bundle_to_out(b) for b in past],
    )


# YooKassa notification IPs — webhook requests must come from these ranges.
# https://yookassa.ru/developers/using-api/webhooks#ips
_YOOKASSA_NOTIFICATION_IPS = {
    # IPv4 ranges kept as prefixes — replace with an ipaddress check later.
    "185.71.76.",
    "185.71.77.",
    "77.75.153.",
    "77.75.154.",
    "77.75.156.",
    "77.75.158.",
    "2a02:5180:",
}


def _is_yookassa_ip(client_host: str) -> bool:
    if not client_host:
        return False
    return any(client_host.startswith(prefix) for prefix in _YOOKASSA_NOTIFICATION_IPS)


@app.post("/bundles/payments/webhook", response_model=StatusOut)
def yookassa_bundle_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive `payment.succeeded` / `payment.canceled` events from YooKassa.
    Complements the polling path — if the user closes the WebView early we
    still get the outcome here and finalise the bundle idempotently.

    We intentionally accept events without shared JWT auth because YooKassa
    calls us directly; instead we guard by IP prefix. Anything that isn't
    `payment.succeeded` is acknowledged but ignored."""
    client = request.client
    client_host = client.host if client else ""
    if not _is_yookassa_ip(client_host):
        # In dev we might hit this endpoint from localhost; don't fail
        # loudly, but tag it so logs make the source obvious.
        print(f"[yookassa_webhook] non-whitelisted IP {client_host}, ignoring")
        return StatusOut(status="ok", message="ignored (non-whitelisted ip)")

    import json as _json
    try:
        body = _json.loads(request.scope.get("_body", b"") or b"{}") if False else None
    except Exception:
        body = None
    # Fallback: read body via sync reader — FastAPI request.body is async;
    # to avoid making this an async def and rewriting every dependency,
    # fetch the JSON from starlette's receive channel synchronously.
    # Simpler: re-declare as async def below.
    return StatusOut(status="ok", message="see async handler")


@app.post("/bundles/payments/webhook-async")
async def yookassa_bundle_webhook_async(
    request: Request,
    db: Session = Depends(get_db),
):
    """Async version of the webhook — YooKassa webhooks should point here.
    Keeps the sync version as a compatibility shim until we can drop it."""
    client = request.client
    client_host = client.host if client else ""
    if not _is_yookassa_ip(client_host):
        print(f"[yookassa_webhook_async] non-whitelisted IP {client_host}")
        return {"status": "ok", "message": "ignored (non-whitelisted ip)"}

    try:
        payload = await request.json()
    except Exception:
        return {"status": "error", "message": "invalid json"}

    event = payload.get("event")
    obj = payload.get("object") or {}
    payment_id = obj.get("id")
    if not payment_id:
        return {"status": "ok", "message": "no payment id"}

    if event != "payment.succeeded":
        print(f"[yookassa_webhook] ignoring event={event}")
        return {"status": "ok", "message": f"ignored {event}"}

    # Idempotent create — if we already have the bundle, do nothing
    existing = db.query(LoungeBundle).filter(
        LoungeBundle.purchase_receipt_id == payment_id,
    ).first()
    if existing:
        return {"status": "ok", "message": "already finalised", "bundle_id": existing.id}

    meta = obj.get("metadata") or {}
    user_id_str = meta.get("user_id")
    tier = meta.get("tier")
    if not user_id_str or not tier:
        return {"status": "error", "message": "missing metadata"}

    try:
        user_id = int(user_id_str)
    except Exception:
        return {"status": "error", "message": "bad user_id"}

    tier_cfg = BUNDLE_TIERS.get(tier)
    if not tier_cfg:
        return {"status": "error", "message": f"unknown tier {tier}"}

    now = datetime.utcnow()
    bundle = LoungeBundle(
        user_id=user_id,
        tier=tier,
        lounge_ids="",
        discount_percent=0,
        max_visits=(tier_cfg["hookahs"] or 0),
        compensation_per_visit_rub=tier_cfg["comp_rub"],
        price_rub=tier_cfg["price_rub"],
        purchase_provider="yookassa",
        purchase_receipt_id=payment_id,
        started_at=now,
        expires_at=now + timedelta(days=tier_cfg["days"]),
        status="active",
    )
    db.add(bundle)
    db.flush()

    db.add(LoungeLedgerEntry(
        brand_id=None,
        user_id=user_id,
        bundle_id=bundle.id,
        direction="inflow",
        amount_rub=tier_cfg["price_rub"],
        status="settled",
        description=f"Bundle sale (webhook) — {tier_cfg['title']}",
        settled_at=now,
    ))

    db.commit()
    return {"status": "ok", "bundle_id": bundle.id}


# ===============================================================
# DEVICE TOKEN — push registration
# ===============================================================

@app.post("/users/me/device-token", response_model=StatusOut)
def register_device_token(
    payload: DeviceTokenIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    token = payload.token.strip()
    if not token:
        raise HTTPException(400, "Empty token")

    existing = db.query(DeviceToken).filter(DeviceToken.token == token).first()
    now = datetime.utcnow()
    if existing:
        existing.user_id = current_user.id  # re-claim if token was on another user
        existing.platform = payload.platform or "ios"
        existing.app_version = payload.app_version
        existing.updated_at = now
    else:
        db.add(DeviceToken(
            user_id=current_user.id,
            token=token,
            platform=payload.platform or "ios",
            app_version=payload.app_version,
            created_at=now,
            updated_at=now,
        ))
    db.commit()
    return StatusOut(status="ok", message="device token saved")


@app.delete("/users/me/device-token", response_model=StatusOut)
def delete_device_token(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current_user = get_required_user(user)
    db.query(DeviceToken).filter(
        DeviceToken.user_id == current_user.id,
        DeviceToken.token == token,
    ).delete(synchronize_session=False)
    db.commit()
    return StatusOut(status="ok", message="device token removed")


# ===============================================================
# APPLE SIGN-IN
# ===============================================================

import httpx as _httpx
import jwt as _pyjwt
from jwt import PyJWKClient as _PyJWKClient

_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUER = "https://appleid.apple.com"
# TODO: replace with real bundle id once set in the Apple Developer Console
_APPLE_AUDIENCE = os.getenv("APPLE_BUNDLE_ID", "com.krasnoe.Hooka3")

_apple_jwk_client = None

def _get_apple_jwk_client():
    global _apple_jwk_client
    if _apple_jwk_client is None:
        _apple_jwk_client = _PyJWKClient(_APPLE_JWKS_URL)
    return _apple_jwk_client


@app.post("/auth/apple", response_model=AppleSignInOut)
def apple_sign_in(
    payload: AppleSignInIn,
    db: Session = Depends(get_db),
):
    """Accept an identity token from Sign in with Apple, verify it against
    Apple's public keys, then create or find a matching user.
    Apple only returns the email on the first auth per app — we persist
    it. The `sub` claim is the stable user id we key by when email is
    unavailable on subsequent calls."""
    try:
        signing_key = _get_apple_jwk_client().get_signing_key_from_jwt(payload.identity_token)
        decoded = _pyjwt.decode(
            payload.identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=_APPLE_AUDIENCE,
            issuer=_APPLE_ISSUER,
        )
    except Exception as exc:
        raise HTTPException(401, f"Apple identity token invalid: {exc}")

    apple_sub = decoded.get("sub")
    apple_email = (payload.email or decoded.get("email") or "").lower().strip()

    if not apple_sub:
        raise HTTPException(401, "Apple token missing sub")

    # Lookup by stable apple_sub proxy — stored in email pattern "apple-sub:{sub}"
    # or by email if the user already exists with that address.
    proxy_email = f"apple-sub-{apple_sub}@apple.hooka3.internal"
    user = None
    if apple_email:
        user = db.query(User).filter(User.email == apple_email).first()
    if user is None:
        user = db.query(User).filter(User.email == proxy_email).first()

    is_new = False
    if user is None:
        # Create user. Username falls back to apple_sub prefix.
        base_username = (payload.full_name or apple_email.split("@")[0] or f"apple{apple_sub[:6]}")
        base_username = "".join(ch for ch in base_username.lower() if ch.isalnum() or ch == "_")[:24] or f"apple{apple_sub[:6]}"
        username = base_username
        suffix = 1
        while db.query(User).filter(User.username == username).first() is not None:
            suffix += 1
            username = f"{base_username}{suffix}"

        user = User(
            email=apple_email or proxy_email,
            username=username,
            password_hash=hashlib.sha256(f"apple-{apple_sub}-no-password".encode()).hexdigest(),
            is_admin=False,
            is_banned=False,
        )
        db.add(user)
        db.flush()
        is_new = True
    elif apple_email and not user.email:
        user.email = apple_email

    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return AppleSignInOut(
        user_id=user.id,
        token=token,
        username=user.username,
        is_new_user=is_new,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)



# ── Wallet endpoints ──

@app.post("/wallet/connect", response_model=WalletBalanceOut)
def wallet_connect(body: WalletConnectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.ton_address = body.ton_address
    db.commit()
    db.refresh(user)
    progress = ensure_user_progress(user, db)
    ugolki = max(progress.points, 0)
    return WalletBalanceOut(user_id=user.id, ton_address=user.ton_address, ugolki_balance=ugolki, hooka_balance=round(ugolki / 100.0, 2))

@app.get("/wallet/balance", response_model=WalletBalanceOut)
def wallet_balance(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    progress = ensure_user_progress(user, db)
    ugolki = max(progress.points, 0)
    return WalletBalanceOut(user_id=user.id, ton_address=getattr(user, "ton_address", None), ugolki_balance=ugolki, hooka_balance=round(ugolki / 100.0, 2))

@app.post("/wallet/mint", response_model=WalletMintOut)
def wallet_mint(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    progress = ensure_user_progress(user, db)
    ugolki = max(progress.points, 0)
    return WalletMintOut(success=True, amount=ugolki, new_ugolki_balance=ugolki, new_hooka_balance=round(ugolki / 100.0, 2), tx_hash=None)

@app.post("/wallet/burn", response_model=WalletBurnOut)
def wallet_burn(amount: int = Query(..., gt=0), reason: str = Query(default="spend"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    progress = ensure_user_progress(user, db)
    if amount > progress.points:
        raise HTTPException(400, f"Not enough: have {progress.points}, need {amount}")
    activity = UserActivity(user_id=user.id, event_type="shop_purchase", points_delta=-amount, rating_delta=0, description=f"Burn: {reason}", created_at=datetime.utcnow())
    db.add(activity)
    progress.points -= amount
    db.commit()
    return WalletBurnOut(success=True, amount=amount, reason=reason, new_ugolki_balance=max(progress.points, 0), new_hooka_balance=round(max(progress.points, 0) / 100.0, 2))

@app.post("/admin/users/{user_id}/set-rating")
def admin_set_rating(user_id: int, rating: int = Query(...), admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    progress = ensure_user_progress(target, db)
    progress.rating = rating
    db.commit()
    return {"user_id": user_id, "new_rating": rating, "level_title": level_title_for_rating(rating)}

@app.post("/admin/users/{user_id}/set-points")
def admin_set_points(user_id: int, points: int = Query(...), admin: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    progress = ensure_user_progress(target, db)
    progress.points = points
    db.commit()
    return {"user_id": user_id, "new_points": points}


# -------------------------------------------------------------------
# DUEL ENDPOINTS
# -------------------------------------------------------------------

# In-memory duel rooms
active_duel_rooms = {}

@app.post("/duels/create", response_model=DuelCreateOut)
def create_duel(body: DuelCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check rate limit: 1 duel per venue per day per user
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    existing = db.query(Duel).filter(
        Duel.guest_user_id == user.id,
        Duel.brand_id == body.brand_id,
        Duel.created_at >= today_start
    ).first()
    if existing and existing.status != "expired":
        raise HTTPException(400, "Already have an active duel at this venue today")

    # Get base discount from tier
    loyalty = db.query(LoungeGuestLoyalty).filter(
        LoungeGuestLoyalty.user_id == user.id,
        LoungeGuestLoyalty.brand_id == body.brand_id
    ).first()
    visit_count = loyalty.visit_count if loyalty else 0
    tier = lounge_tier_for_visits(visit_count)
    base = tier.discount_percent
    duel = base * 2 if base * 2 <= 30 else 30

    join_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    duel_id = str(uuid.uuid4())[:8]

    d = Duel(id=duel_id, brand_id=body.brand_id, guest_user_id=user.id,
             base_discount=base, duel_discount=duel, join_code=join_code)
    db.add(d)
    db.commit()

    return DuelCreateOut(duel_id=duel_id, join_code=join_code,
                         base_discount=base, duel_discount=duel, status="waiting")

@app.post("/duels/join", response_model=DuelStateOut)
def join_duel(body: DuelJoinIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(Duel).filter(Duel.join_code == body.join_code, Duel.status == "waiting").first()
    if not d:
        raise HTTPException(404, "Duel not found or already started")
    d.host_user_id = user.id
    d.status = "active"
    d.started_at = datetime.utcnow()
    db.commit()

    guest = db.query(User).filter(User.id == d.guest_user_id).first()
    return DuelStateOut(duel_id=d.id, brand_id=d.brand_id,
                       guest_username=guest.username if guest else None,
                       host_username=user.username,
                       status=d.status, guest_score=0, host_score=0,
                       winner_id=None, base_discount=d.base_discount,
                       duel_discount=d.duel_discount)

@app.get("/duels/{duel_id}", response_model=DuelStateOut)
def get_duel(duel_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(Duel).filter(Duel.id == duel_id).first()
    if not d:
        raise HTTPException(404, "Duel not found")
    guest = db.query(User).filter(User.id == d.guest_user_id).first()
    host = db.query(User).filter(User.id == d.host_user_id).first() if d.host_user_id else None
    return DuelStateOut(duel_id=d.id, brand_id=d.brand_id,
                       guest_username=guest.username if guest else None,
                       host_username=host.username if host else None,
                       status=d.status, guest_score=d.guest_score, host_score=d.host_score,
                       winner_id=d.winner_id, base_discount=d.base_discount,
                       duel_discount=d.duel_discount)

@app.get("/duels/pending/{brand_id}")
def get_pending_duels(brand_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    duels = db.query(Duel).filter(Duel.brand_id == brand_id, Duel.status == "waiting").all()
    return [{"duel_id": d.id, "join_code": d.join_code, "guest_user_id": d.guest_user_id,
             "duel_discount": d.duel_discount} for d in duels]

@app.websocket("/ws/duel/{duel_id}")
async def duel_websocket(websocket: WebSocket, duel_id: str):
    await websocket.accept()

    # Get token from query params
    token = websocket.query_params.get("token", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Initialize room
    if duel_id not in active_duel_rooms:
        active_duel_rooms[duel_id] = {"players": {}, "scores": {}, "ready": set()}

    room = active_duel_rooms[duel_id]
    room["players"][str(user_id)] = websocket
    room["scores"][str(user_id)] = 0

    try:
        # Notify opponent joined
        if len(room["players"]) == 2:
            for uid, ws in room["players"].items():
                opponent_id = [k for k in room["players"] if k != uid][0]
                await ws.send_json({"type": "opponent_joined", "opponent_id": opponent_id})

        while True:
            data = await websocket.receive_json()

            if data["type"] == "ready":
                room["ready"].add(str(user_id))
                if len(room["ready"]) == 2:
                    # Countdown
                    for i in [3, 2, 1]:
                        for ws in room["players"].values():
                            await ws.send_json({"type": "countdown", "value": i})
                        await asyncio.sleep(1)
                    for ws in room["players"].values():
                        await ws.send_json({"type": "start"})

            elif data["type"] == "score_update":
                room["scores"][str(user_id)] = data["score"]
                # Send to opponent
                for uid, ws in room["players"].items():
                    if uid != str(user_id):
                        await ws.send_json({
                            "type": "opponent_score",
                            "score": data["score"],
                            "combo": data.get("combo", 0)
                        })

            elif data["type"] == "final_score":
                room["scores"][str(user_id)] = data["score"]
                # Check if both submitted
                if all(room["scores"].get(uid, -1) >= 0 for uid in room["players"]):
                    scores = room["scores"]
                    uids = list(scores.keys())
                    s0, s1 = scores[uids[0]], scores[uids[1]]

                    if s0 > s1:
                        winner = int(uids[0])
                    elif s1 > s0:
                        winner = int(uids[1])
                    else:
                        winner = None  # draw

                    # Save to DB
                    finish_db = SessionLocal()
                    try:
                        d = finish_db.query(Duel).filter(Duel.id == duel_id).first()
                        if d:
                            d.guest_score = scores.get(str(d.guest_user_id), 0)
                            d.host_score = scores.get(str(d.host_user_id), 0)
                            d.winner_id = winner
                            d.status = "finished"
                            d.finished_at = datetime.utcnow()
                            finish_db.commit()
                    finally:
                        finish_db.close()

                    # Notify both
                    for uid, ws in room["players"].items():
                        await ws.send_json({
                            "type": "result",
                            "winner_id": winner,
                            "your_score": scores[uid],
                            "opponent_score": scores[[k for k in scores if k != uid][0]],
                            "discount": d.duel_discount if winner == int(uid) else (d.base_discount if winner is None else 0)
                        })

                    del active_duel_rooms[duel_id]

    except WebSocketDisconnect:
        # Auto-win for remaining player
        if duel_id in active_duel_rooms:
            room = active_duel_rooms[duel_id]
            for uid, ws in room["players"].items():
                if uid != str(user_id):
                    try:
                        await ws.send_json({
                            "type": "result",
                            "winner_id": int(uid),
                            "your_score": room["scores"].get(uid, 0),
                            "opponent_score": 0,
                            "discount": 10,
                            "reason": "opponent_disconnected"
                        })
                    except Exception:
                        pass
            del active_duel_rooms[duel_id]



# ── Pending Duel Offer (guest-side notification) ──

@app.get("/me/pending-duel-offer")
def get_pending_duel_offer(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if guest has a pending duel offer after venue check-in."""
    from sqlalchemy import text
    result = db.execute(
        text("SELECT id, brand_id, discount_percent, created_at FROM pending_duel_offers WHERE user_id = :uid AND consumed = FALSE ORDER BY created_at DESC LIMIT 1"),
        {"uid": user.id}
    ).fetchone()
    if not result:
        return {"has_offer": False}
    return {
        "has_offer": True,
        "offer_id": result[0],
        "brand_id": result[1],
        "discount_percent": result[2],
        "created_at": str(result[3])
    }

@app.post("/me/pending-duel-offer/{offer_id}/consume")
def consume_duel_offer(offer_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark a pending duel offer as consumed."""
    from sqlalchemy import text
    db.execute(
        text("UPDATE pending_duel_offers SET consumed = TRUE WHERE id = :oid AND user_id = :uid"),
        {"oid": offer_id, "uid": user.id}
    )
    db.commit()
    return {"status": "ok"}

# ── Duel WebSocket ──────────────────────────────────────────────────────────
from typing import Dict as _Dict

class DuelConnectionManager:
    def __init__(self):
        self.connections = {}  # duel_id -> [(ws, user_id)]
        self.ready = {}
        self.scores = {}

    async def connect(self, duel_id: str, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if duel_id not in self.connections:
            self.connections[duel_id] = []
            self.ready[duel_id] = set()
            self.scores[duel_id] = {}
        self.connections[duel_id].append((websocket, user_id))
        await self.broadcast(duel_id, {"type": "opponent_joined", "user_id": user_id}, exclude=websocket)
        if len(self.connections[duel_id]) >= 2:
            await self.start_countdown(duel_id)

    async def disconnect(self, duel_id: str, websocket: WebSocket):
        if duel_id in self.connections:
            self.connections[duel_id] = [(ws, uid) for ws, uid in self.connections[duel_id] if ws != websocket]
            await self.broadcast(duel_id, {"type": "opponent_disconnected"}, exclude=websocket)

    async def broadcast(self, duel_id: str, message: dict, exclude=None):
        if duel_id not in self.connections:
            return
        dead = []
        for ws, uid in self.connections[duel_id]:
            if ws == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append((ws, uid))
        for d in dead:
            self.connections[duel_id].remove(d)

    async def start_countdown(self, duel_id: str):
        for i in [3, 2, 1]:
            await self.broadcast_all(duel_id, {"type": "countdown", "value": i})
            await asyncio.sleep(1)
        await self.broadcast_all(duel_id, {"type": "start"})
        asyncio.create_task(self.end_game(duel_id))

    async def broadcast_all(self, duel_id: str, message: dict):
        if duel_id not in self.connections:
            return
        dead = []
        for ws, uid in self.connections[duel_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append((ws, uid))
        for d in dead:
            self.connections[duel_id].remove(d)

    async def handle_score_update(self, duel_id: str, user_id: int, score: int, combo: int, heat: float, websocket):
        self.scores[duel_id][user_id] = {"score": score, "combo": combo, "heat": heat}
        await self.broadcast(duel_id, {"type": "opponent_score", "score": score, "combo": combo, "heat": heat}, exclude=websocket)

    async def handle_final_score(self, duel_id: str, user_id: int, score: int, db):
        self.scores[duel_id]["final_" + str(user_id)] = score
        finals = {k: v for k, v in self.scores[duel_id].items() if str(k).startswith("final_")}
        if len(finals) >= 2 or len(self.connections.get(duel_id, [])) <= 1:
            await self.end_game(duel_id, db=db)

    async def end_game(self, duel_id: str, db=None):
        scores = {k: v for k, v in self.scores.get(duel_id, {}).items() if str(k).startswith("final_")}
        if not scores:
            scores = {"raw_" + str(k): v["score"] for k, v in self.scores.get(duel_id, {}).items() if isinstance(v, dict)}
        winner_id = None
        result_msg = {"type": "result", "winner_id": None, "is_draw": True, "discount": 5}
        if scores and db:
            try:
                duel = db.query(Duel).filter(Duel.id == duel_id).first()
                if duel:
                    score_items = list(scores.items())
                    if len(score_items) >= 2:
                        uid1 = int(str(score_items[0][0]).replace("final_", "").replace("raw_", ""))
                        s1 = score_items[0][1]
                        uid2 = int(str(score_items[1][0]).replace("final_", "").replace("raw_", ""))
                        s2 = score_items[1][1]
                        winner_id = uid1 if s1 > s2 else (uid2 if s2 > s1 else None)
                    duel.winner_id = winner_id
                    duel.status = "finished"
                    duel.guest_score = score_items[0][1] if score_items else 0
                    duel.host_score = score_items[1][1] if len(score_items) > 1 else 0
                    db.commit()
                    result_msg = {
                        "type": "result",
                        "winner_id": winner_id,
                        "is_draw": winner_id is None,
                        "duel_discount": getattr(duel, "duel_discount", None),
                        "base_discount": getattr(duel, "base_discount", None),
                    }
            except Exception as e:
                print("end_game error:", e)
        await self.broadcast_all(duel_id, result_msg)


duel_manager = DuelConnectionManager()


@app.websocket("/ws/duel/{duel_id}")
async def duel_websocket(duel_id: str, websocket: WebSocket, token: str = None, db: Session = Depends(get_db)):
    user_id = None
    if token:
        try:
            from jose import jwt as jose_jwt
            payload = jose_jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("sub") or payload.get("user_id") or payload.get("id")
            user_id = int(user_id)
        except Exception as e:
            print("WS auth error:", e)
            await websocket.close(code=4001)
            return
    await duel_manager.connect(duel_id, websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            print("[WS] duel=" + str(duel_id) + " user=" + str(user_id) + " type=" + str(msg_type))
            if msg_type == "ready":
                duel_manager.ready[duel_id].add(user_id)
                if len(duel_manager.ready[duel_id]) >= 2:
                    await duel_manager.start_countdown(duel_id)
            elif msg_type == "score_update":
                await duel_manager.handle_score_update(
                    duel_id, user_id,
                    data.get("score", 0),
                    data.get("combo", 0),
                    data.get("heat", 0.0),
                    websocket
                )
            elif msg_type == "final_score":
                await duel_manager.handle_final_score(
                    duel_id, user_id,
                    data.get("score", 0),
                    db
                )
    except WebSocketDisconnect:
        await duel_manager.disconnect(duel_id, websocket)
    except Exception as e:
        print("[WS] error duel=" + str(duel_id) + ":", e)
        await duel_manager.disconnect(duel_id, websocket)
