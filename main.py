import re
import uuid
import random
import string
import asyncio
import urllib.parse
from fastapi import WebSocket, WebSocketDisconnect
import hashlib
import bcrypt
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, text as sa_text
from sqlalchemy.exc import IntegrityError
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
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    security,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.models import (
    BonusRedemption,
    Duel,
    BowlHeatRun,
    Comment,
    Event,
    EventRSVP,
    Favorite,
    FeaturedSlot,
    LoungeAdminMeta,
    LoungeAssets,
    LoungeBundle,
    LoungeBillingSubscription,
    LoungeBundleVisit,
    LoungeBusinessEvent,
    LoungeGuestLoyalty,
    LoungeGuestPersonalization,
    LoungeOwnerCredentials,
    LoungePromo,
    LoungePromotedSlot,
    LoungeSubscription,
    LoungeVisit,
    DeviceToken,
    LoungeLedgerEntry,
    LoungeLoyaltyProgram,
    LoungeProgram,
    ManagerTelegramLink,
    Master,
    MasterFollower,
    MasterLoungeRequest,
    MasterReview,
    MasterShift,
    MasterWorkHistory,
    Mix,
    MixIngredient,
    MonthlyVote,
    User,
    UserActivity,
    UserFollow,
    UserMedal,
    UserProgress,
    RefreshToken,
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
    EventIn,
    EventOut,
    EventRSVPIn,
    EventRSVPOut,
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
    MasterCreateIn,
    MasterListOut,
    MasterLoungeRequestIn,
    MasterLoungeRequestOut,
    MasterOut,
    MasterReviewCreateIn,
    MasterReviewOut,
    MasterReviewsListOut,
    MasterResponseCreateIn,
    MasterResponseOut,
    MasterGuestStatsOut,
    MasterGuestVisitOut,
    MasterShiftCreateIn,
    MasterShiftOut,
    MasterShiftsListOut,
    MasterUpdateIn,
    MasterWorkHistoryAddIn,
    MasterWorkHistoryAddOut,
    MasterWorkplaceOut,
    MixCreate,
    MixGenerateIn,
    MixGenerateOut,
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
    LeaderboardEntryOut,
    LeaderboardOut,
    MedalBackfillOut,
    MedalCountsOut,
    UserMedalOut,
    UserPublicStatsOut,
    LoungeAssetsIn,
    LoungeAssetsOut,
    LoungeBusynessOut,
    LoungeRefreshBusynessIn,
    TelegramLinkCodeOut,
    TelegramLinkStatusOut,
    AccountDeleteOut,
    MasterAvatarUploadIn,
    LoungeImageUploadIn,
    TobaccoFlavorOut,
    TobaccoFlavorListOut,
    TobaccoBrandOut,
    TobaccoBrandListOut,
    TobaccoBrandFlavorsOut,
    TobaccoMixTemplateIngredientOut,
    TobaccoMixTemplateOut,
    TobaccoMixTemplateListOut,
    LoungeSubscriptionIn,
    LoungeSubscriptionDTO,
    LoungeLoyaltyProgramIn,
    LoungeLoyaltyProgramOut,
    LoungePromoIn,
    LoungePromoOut,
    LoungePromoUpdateIn,
    LoungePromoListOut,
    TokenRefreshRequest,
    TokenRefreshResponse,
    LogoutRequest,
    HourBucket,
    WeekdayBucket,
    LoungeCrmStatsOut,
    LoungeCrmRegularOut,
    LoungeCrmRegularsOut,
    GuestVisitRowOut,
    LoungeCrmGuestCardOut,
    GuestBalanceOut,
    RedeemIn,
    RedemptionRowOut,
    RedemptionListOut,
    PromotedLoungeOut,
    PromotedListOut,
    PromotedSlotIn,
    FeaturedSlotOut,
    FeaturedSlotIn,
    FeaturedFeedOut,
    FlavorPopularity,
    RegionBucket,
    BrandAnalyticsOut,
    LoungeMyBonusItemOut,
    LoungeMyBonusesOut,
    LoungeAdminMetaOut,
    LoungeAdminMetaIn,
    LoungeAdminListItemOut,
    LoungePublicMetaOut,
    LoungeBillingSubscriptionOut,
    LoungeBillingSubscriptionGrantIn,
    LoungeCheckoutIn,
    LoungeCheckoutOut,
    VALID_LOUNGE_TIERS,
    VALID_LOUNGE_BADGES,
    LoungeCRMHeatmapCellOut,
    LoungeCRMHeatmapOut,
    HighlightCardIn,
    HighlightCardOut,
    LoungeHighlightsIn,
    LoungeHighlightsOut,
    LoungeHighlightPhotoOut,
    EventPhotoOut,
    LoungePushIn,
)
from app.services.subscriptions import get_active_tier, require_tier

# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    """Хеширует пароль bcrypt. Для legacy-сравнения используется
    `verify_password`, который понимает оба формата (bcrypt + SHA-256)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hash_: str) -> bool:
    """Проверяет пароль. Поддерживает bcrypt (новый, начинается с `$2`)
    и SHA-256 (legacy, шестнадцать-байтовый hex). Не падает при пустом hash."""
    if not hash_:
        return False
    if hash_.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hash_.encode("utf-8"))
        except Exception:
            return False
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return legacy == hash_


def password_needs_rehash(hash_: str) -> bool:
    """True для legacy SHA-256 хэшей — после успешного логина перезаписываем
    в bcrypt без явного действия пользователя."""
    return not (hash_ or "").startswith("$2")


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

    # MARK: App Store 5.1.1(v) — soft-deleted accounts cannot authenticate
    # for any subsequent request. PII has been scrubbed; treat as logged-out
    # but with a 403 so the iOS client can handle it like a permanent ban.
    if user and getattr(user, "is_deleted", False):
        raise HTTPException(403, "Account deleted")

    return user


def get_admin_user(
    user: User = Depends(get_current_user)
) -> User:
    if not user:
        raise HTTPException(401, "Unauthorized")
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user


def _decode_mix_tags(raw: Optional[str]) -> List[str]:
    """Mix.tags is stored as a JSON-encoded list (TEXT). Decode defensively
    so a malformed legacy row never crashes the API."""
    if not raw:
        return []
    import json as _json
    try:
        decoded = _json.loads(raw)
    except Exception:
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded if item is not None]


def is_mix_partner(brand_id: Optional[str], db: Session) -> bool:
    """Return True when the lounge brand has the 'mix_partner' badge in lounge_admin_meta."""
    if not brand_id:
        return False
    meta = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if not meta:
        return False
    badges = meta.badges if isinstance(meta.badges, list) else []
    return "mix_partner" in badges


def mix_to_out(mix: Mix, user: Optional[User], db: Session):
    likes_count = db.query(Favorite)\
        .filter(Favorite.mix_id == mix.id).count()

    comments_count = db.query(Comment)\
        .filter(Comment.mix_id == mix.id).count()

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
        comments_count=comments_count,
        is_liked=is_liked,
        is_author_followed=is_author_followed,
        status=(mix.status or "public"),
        lounge_id=mix.lounge_id,
        tags=_decode_mix_tags(mix.tags),
        lounge_partner_badge=is_mix_partner(mix.lounge_id, db),
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
        avatar_url=profile_user.avatar_url,
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
BRAND_MANAGER_ALIASES = {
    "secret_yauza": {"secret_lounge_yauza"},
    "secret_lounge_yauza": {"secret_yauza"},
}


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
    candidates = {brand_id, *BRAND_MANAGER_ALIASES.get(brand_id, set())}
    managers: set[str] = set()
    for candidate in candidates:
        managers.update(BRAND_MANAGER_USERNAMES.get(candidate, set()))
        managers.update(DEFAULT_BRAND_MANAGER_USERNAMES.get(candidate, set()))
    return {username.lower() for username in managers}


def can_manage_brand(user: Optional[User], brand_id: str, db: Optional[Session] = None) -> bool:
    if not user:
        return False
    if user.is_admin:
        return True

    allowed = resolve_brand_managers(brand_id)
    email = normalize_key(user.email)
    username = normalize_key(user.username)
    if username in allowed or email in allowed:
        return True

    # Convention: lounge owner username equals brand_id slug
    if username and username == normalize_key(brand_id):
        return True

    # DB check: lounge_owner_credentials row links this user to this brand
    if db is not None:
        try:
            row = db.query(LoungeOwnerCredentials).filter(
                LoungeOwnerCredentials.brand_id == brand_id,
                LoungeOwnerCredentials.user_id == user.id,
            ).first()
            if row is not None:
                return True
        except Exception:
            pass

    return False


def _gen_owner_password() -> str:
    """Generate a readable password like Lounge-Ab3X9."""
    chars = string.ascii_letters + string.digits
    suffix = "".join(random.choices(chars, k=5))
    return f"Lounge-{suffix}"


def ensure_lounge_owner(brand_id: str, db: Session, title: Optional[str] = None) -> dict:
    """
    Idempotent: if lounge_owner_credentials row exists, return it.
    Otherwise create a User (account_type='lounge_owner') and the creds row.
    Returns dict with keys: email, username, password, user_id.
    """
    existing = db.query(LoungeOwnerCredentials).filter(
        LoungeOwnerCredentials.brand_id == brand_id
    ).first()
    if existing:
        return {
            "email": existing.email,
            "username": existing.username,
            "password": existing.password_plain,
            "user_id": existing.user_id,
        }

    email = f"{brand_id}@ember.app"
    username = brand_id

    # Check if user with that email already exists
    user_row = db.query(User).filter(User.email == email).first()
    if user_row is None:
        # Also check by username (same slug)
        user_row = db.query(User).filter(User.username == username).first()

    password = _gen_owner_password()

    if user_row is None:
        # Try preferred username; if taken, fall back to brand_id_owner
        chosen_username = username
        username_taken = db.query(User).filter(User.username == chosen_username).first()
        if username_taken:
            chosen_username = f"{brand_id}_owner"
        user_row = User(
            email=email,
            username=chosen_username,
            password_hash=hash_password(password),
            account_type="lounge_owner",
            is_admin=False,
            is_banned=False,
        )
        db.add(user_row)
        db.flush()
    else:
        # Reuse existing user — update password to the generated one
        user_row.password_hash = hash_password(password)
        db.flush()

    creds = LoungeOwnerCredentials(
        brand_id=brand_id,
        user_id=user_row.id,
        email=user_row.email,
        username=user_row.username or username,
        password_plain=password,
    )
    db.add(creds)
    db.commit()

    return {
        "email": creds.email,
        "username": creds.username,
        "password": creds.password_plain,
        "user_id": creds.user_id,
    }


def require_admin(user: Optional[User] = Depends(get_current_user)) -> User:
    """Dependency: raises 403 unless the caller is an admin.
    MVP: user.is_admin flag OR user.id == 1 (dorfden).
    """
    if not user:
        raise HTTPException(401, "Unauthorized")
    if not user.is_admin and user.id != 1:
        raise HTTPException(403, "Admin access required")
    return user


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

    bonus_balance = (loyalty.bonus_balance or 0) if loyalty else 0
    return LoungeMyLoyaltyOut(
        brand_id=brand_id,
        visit_count=visit_count,
        last_visit_at=loyalty.last_visit_at if loyalty else None,
        tier=tier,
        program=program_out,
        personalization=personalization_out,
        bonus_balance=bonus_balance,
        bonus_rub=bonus_balance // 10,
    )


def record_lounge_event(
    brand_id: str,
    event_type: str,
    db: Session,
    actor_user_id: Optional[int] = None,
    guest_user_id: Optional[int] = None,
    master_id: Optional[str] = None,
):
    db.add(
        LoungeBusinessEvent(
            brand_id=brand_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            guest_user_id=guest_user_id,
            master_id=master_id,
        )
    )


EVENT_KINDS = {"battle", "promo", "dj", "workshop", "tasting", "holiday", "opening", "charity"}


def _clean_event_tags(tags: Optional[list[str]]) -> list[str]:
    clean = []
    for tag in tags or []:
        if not isinstance(tag, str):
            continue
        value = tag.strip()
        if value and value not in clean:
            clean.append(value)
    return clean[:12]


def _decode_json_text(raw: Optional[str], fallback):
    if not raw:
        return fallback
    try:
        parsed = json.loads(raw)
        return parsed if parsed is not None else fallback
    except Exception:
        return fallback


def _event_to_out(event: Event, current_user_id: Optional[int], db: Session) -> EventOut:
    going_count = db.query(EventRSVP).filter(
        EventRSVP.event_id == event.id,
        EventRSVP.going == True,  # noqa: E712
    ).count()
    is_going = False
    if current_user_id is not None:
        is_going = db.query(EventRSVP).filter(
            EventRSVP.event_id == event.id,
            EventRSVP.user_id == current_user_id,
            EventRSVP.going == True,  # noqa: E712
        ).first() is not None

    return EventOut(
        id=str(event.id),
        title=event.title,
        subtitle=event.subtitle,
        kind=event.kind or "promo",
        mood=event.mood or "warm",
        lounge_id=event.lounge_id,
        venue_title=event.venue_title,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        recurrence=_decode_json_text(event.recurrence, None),
        cover_image_url=event.cover_image_url,
        price_text=event.price_text,
        booking_url=event.booking_url,
        tags=list(event.tags or []),
        going_count=going_count,
        is_going=is_going,
    )


def _apply_event_payload(event: Event, payload: EventIn, current_user: User):
    title = payload.title.strip()
    if not title:
        raise HTTPException(400, "Event title cannot be empty")
    if payload.ends_at is not None and payload.ends_at <= payload.starts_at:
        raise HTTPException(400, "ends_at must be after starts_at")
    kind = (payload.kind or "promo").strip().lower()
    if kind not in EVENT_KINDS:
        raise HTTPException(400, f"Unknown event kind '{payload.kind}'")

    event.title = title
    event.subtitle = (payload.subtitle or "").strip() or None
    event.kind = kind
    event.mood = (payload.mood or "warm").strip().lower()
    event.lounge_id = (payload.lounge_id or "").strip() or None
    event.venue_title = (payload.venue_title or "").strip() or None
    event.starts_at = payload.starts_at
    event.ends_at = payload.ends_at
    event.recurrence = json.dumps(payload.recurrence, ensure_ascii=False) if payload.recurrence else None
    raw_cover = (payload.cover_image_url or "").strip()
    if raw_cover.startswith("data:image"):
        # Legacy iOS path — base64 data-URIs must NOT be stored.
        # Client should upload via POST /events/photo and pass the returned URL.
        raw_cover = None
    event.cover_image_url = raw_cover or None
    event.price_text = (payload.price_text or "").strip() or None
    event.booking_url = (payload.booking_url or "").strip() or None
    event.tags = _clean_event_tags(payload.tags)  # Python list → text[] на проде
    event.updated_by_user_id = current_user.id
    event.updated_at = datetime.utcnow()


def _resolve_checkin_master(
    master_id: Optional[str],
    brand_id: str,
    db: Session,
) -> Optional[Master]:
    if not master_id:
        return None
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    if master.current_lounge_id == brand_id:
        return master
    now = datetime.utcnow()
    active_shift = db.query(MasterShift).filter(
        MasterShift.master_id == master_id,
        MasterShift.lounge_id == brand_id,
        MasterShift.starts_at <= now,
        MasterShift.ends_at >= now,
    ).first()
    if active_shift:
        return master
    raise HTTPException(400, "Master is not working in this lounge now")


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
    bundle_visits = db.query(LoungeBundleVisit).options(
        joinedload(LoungeBundleVisit.bundle)
    ).filter(
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
        recent_bundle_visits.append(BundleRecentVisitOut(
            id=v.id,
            tier=v.bundle.tier if v.bundle else "unknown",
            visited_at=v.visited_at,
            compensation_rub=v.compensation_rub,
            master_id=v.master_id,
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
    db.query(EventRSVP).filter(
        EventRSVP.user_id == user.id
    ).delete(synchronize_session=False)
    db.query(Event).filter(
        Event.created_by_user_id == user.id
    ).update(
        {"created_by_user_id": None},
        synchronize_session=False
    )
    db.query(Event).filter(
        Event.updated_by_user_id == user.id
    ).update(
        {"updated_by_user_id": None},
        synchronize_session=False
    )
    db.query(MasterLoungeRequest).filter(
        MasterLoungeRequest.requested_by == user.id
    ).update(
        {"requested_by": None},
        synchronize_session=False
    )
    db.query(MasterLoungeRequest).filter(
        MasterLoungeRequest.decided_by == user.id
    ).update(
        {"decided_by": None},
        synchronize_session=False
    )
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


def get_mix_cover_url(mix: Mix, db: Session) -> str:
    """
    Get cover_url for a mix from lounge assets.
    Priority:
    1. If mix has brands in ingredients, fetch LoungeAssets.cover_url for first brand
    2. Fallback to rotating Unsplash hookah photos
    Always returns a non-empty string.
    """
    brands = [ingredient.brand for ingredient in mix.ingredients if ingredient.brand]

    if brands:
        # Try to get cover from first brand's lounge assets
        for brand in brands:
            lounge_asset = db.query(LoungeAssets).filter(
                LoungeAssets.brand_id == brand
            ).first()
            if lounge_asset and lounge_asset.cover_url:
                return lounge_asset.cover_url

    # Fallback: rotate through 3 Unsplash hookah photos based on mix id
    unsplash_photos = [
        "https://images.unsplash.com/photo-1536663815808-535e2280d2c2?w=1200&h=675&fit=crop&q=80",
        "https://images.unsplash.com/photo-1485872299712-4b80e6bc0002?w=1200&h=675&fit=crop&q=80",
        "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=1200&h=675&fit=crop&q=80",
    ]
    return unsplash_photos[mix.id % len(unsplash_photos)]


def vote_mix_to_out(mix: Mix, percentage: float, cover_url: str = "") -> VoteMixOut:
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
        image_name=mix.bowl_image_name,
        cover_url=cover_url
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
        vote_mix_to_out(mix, score / total_score, get_mix_cover_url(mix, db))
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

# -------------------------------------------------------------------
# JINJA2 TEMPLATES — admin web CRM
# -------------------------------------------------------------------
_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)

# -------------------------------------------------------------------
# RATE LIMITING (slowapi)
# -------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute", "30/second"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# MARK: Static files — uploads (avatars, attachments) live here. The
# /static directory is created lazily on first upload so this mount is
# always safe even on a fresh container.
_STATIC_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(_STATIC_ROOT, exist_ok=True)
app.mount("/static", StaticFiles(directory=_STATIC_ROOT), name="static")


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
        # MARK: Masters domain — Phase 1 migrations (additive, no DROP)
        # Extend users table
        conn.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS account_type VARCHAR(20) DEFAULT 'user'
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS master_profile_id VARCHAR(40)
            """
        )
        # MARK: account-deletion (App Store 5.1.1(v)) — additive soft-delete flag.
        # DELETE /users/me toggles this on. All auth dependency checks must
        # reject deleted accounts.
        conn.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE users
            SET is_deleted = FALSE
            WHERE is_deleted IS NULL
            """
        )
        # Legal consent timestamp — 152-FZ / App Store compliance (2026-05-26)
        conn.exec_driver_sql(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS accepted_terms_at TIMESTAMPTZ
            """
        )
        # Extend existing 'masters' table (created in S192-S194)
        # with additional columns needed for Phase 1+2
        conn.exec_driver_sql(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS reviews_count INTEGER DEFAULT 0
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)
            """
        )
        conn.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ix_masters_user_id
            ON masters(user_id) WHERE user_id IS NOT NULL
            """
        )
        # Extend existing 'master_reviews' table with response fields
        conn.exec_driver_sql(
            """
            ALTER TABLE master_reviews
            ADD COLUMN IF NOT EXISTS master_response_text TEXT
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE master_reviews
            ADD COLUMN IF NOT EXISTS master_responded_at TIMESTAMP
            """
        )
        conn.exec_driver_sql(
            """
            ALTER TABLE master_reviews
            ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE
            """
        )
        conn.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_master_reviews_master_user
            ON master_reviews(master_id, user_id)
            """
        )
        # MARK: Mix Wizard — extend mixes with status / lounge_id / tags (S2026-04-29)
        # Zero-downtime: idempotent ADD COLUMN IF NOT EXISTS, defaults backfill old rows.
        # tags stored as TEXT (JSON-encoded list) to match LoungeAssets pattern and
        # avoid PG vs sqlite JSONB drift.
        # ALTER TABLE … ADD COLUMN IF NOT EXISTS is PG-only — sqlite doesn't
        # support the IF NOT EXISTS clause and will raise. On sqlite the local
        # dev DB is bootstrapped fresh from create_all() above, so the columns
        # are already present and these ALTERs would be no-ops anyway.
        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql(
                """
                ALTER TABLE mixes
                ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'public'
                """
            )
            conn.exec_driver_sql(
                """
                ALTER TABLE mixes
                ADD COLUMN IF NOT EXISTS lounge_id VARCHAR
                """
            )
            conn.exec_driver_sql(
                """
                ALTER TABLE mixes
                ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT '[]'
                """
            )
            conn.exec_driver_sql(
                """
                UPDATE mixes
                SET status = 'public'
                WHERE status IS NULL
                """
            )
            conn.exec_driver_sql(
                """
                UPDATE mixes
                SET tags = '[]'
                WHERE tags IS NULL
                """
            )

            # MARK: Master shifts — расписание смен мастера (S2026-04-29)
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS master_shifts (
                    id SERIAL PRIMARY KEY,
                    master_id VARCHAR NOT NULL REFERENCES masters(id) ON DELETE CASCADE,
                    lounge_id TEXT NOT NULL,
                    starts_at TIMESTAMP NOT NULL,
                    ends_at TIMESTAMP NOT NULL,
                    note TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_master_shifts_master_starts
                ON master_shifts(master_id, starts_at)
                """
            )
            # MARK: Master lounge requests — master asks venue owner to approve attachment.
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS master_lounge_requests (
                    id SERIAL PRIMARY KEY,
                    master_id VARCHAR NOT NULL REFERENCES masters(id) ON DELETE CASCADE,
                    lounge_id TEXT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    requested_by INTEGER REFERENCES users(id),
                    decided_by INTEGER REFERENCES users(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    decided_at TIMESTAMP
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_master_lounge_requests_lounge_status
                ON master_lounge_requests(lounge_id, status, created_at)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_master_lounge_requests_master_status
                ON master_lounge_requests(master_id, status)
                """
            )
            # MARK: Lounge events / promos — real backend for iOS EventStore.
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id VARCHAR PRIMARY KEY,
                    title VARCHAR NOT NULL,
                    subtitle TEXT,
                    kind VARCHAR(40) NOT NULL DEFAULT 'promo',
                    mood VARCHAR(40) NOT NULL DEFAULT 'warm',
                    lounge_id VARCHAR,
                    venue_title VARCHAR,
                    starts_at TIMESTAMP NOT NULL,
                    ends_at TIMESTAMP,
                    recurrence TEXT,
                    cover_image_url TEXT,
                    price_text VARCHAR,
                    booking_url TEXT,
                    tags TEXT DEFAULT '[]',
                    created_by_user_id INTEGER REFERENCES users(id),
                    updated_by_user_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            for ddl in [
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS subtitle TEXT",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS kind VARCHAR(40) DEFAULT 'promo'",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS mood VARCHAR(40) DEFAULT 'warm'",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS lounge_id VARCHAR",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS venue_title VARCHAR",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS starts_at TIMESTAMP DEFAULT NOW()",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS ends_at TIMESTAMP",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS recurrence TEXT",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS cover_image_url TEXT",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS price_text VARCHAR",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS booking_url TEXT",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS tags TEXT DEFAULT '[]'",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES users(id)",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS updated_by_user_id INTEGER REFERENCES users(id)",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
                "ALTER TABLE events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            ]:
                conn.exec_driver_sql(ddl)
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_events_lounge_starts
                ON events(lounge_id, starts_at)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS event_rsvps (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    going BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(event_id, user_id)
                )
                """
            )
            for ddl in [
                "ALTER TABLE event_rsvps ADD COLUMN IF NOT EXISTS event_id VARCHAR REFERENCES events(id) ON DELETE CASCADE",
                "ALTER TABLE event_rsvps ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)",
                "ALTER TABLE event_rsvps ADD COLUMN IF NOT EXISTS going BOOLEAN DEFAULT TRUE",
                "ALTER TABLE event_rsvps ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            ]:
                conn.exec_driver_sql(ddl)
            conn.exec_driver_sql(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_event_rsvps_event_user
                ON event_rsvps(event_id, user_id)
                """
            )
            # Master attribution for QR check-ins and bundle redemptions.
            conn.exec_driver_sql(
                """
                ALTER TABLE lounge_business_events
                ADD COLUMN IF NOT EXISTS master_id VARCHAR REFERENCES masters(id)
                """
            )
            conn.exec_driver_sql(
                """
                ALTER TABLE lounge_bundle_visits
                ADD COLUMN IF NOT EXISTS master_id VARCHAR REFERENCES masters(id)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_lounge_business_events_master
                ON lounge_business_events(master_id, created_at)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_lounge_bundle_visits_master
                ON lounge_bundle_visits(master_id, visited_at)
                """
            )
    db = SessionLocal()
    try:
        sync_admin_allowlist(db)
    finally:
        db.close()

    # MARK: user_medals (LOOMIX parity, S2026-05-15)
    # Base.metadata.create_all() above already creates the table from the
    # UserMedal SQLAlchemy model. On production PostgreSQL we additionally
    # run idempotent raw DDL for the explicit unique + indices so the
    # constraints survive on environments where the table was created by
    # a prior partial migration. Sqlite (local dev) is bootstrapped fresh
    # from create_all() so we skip the raw DDL there — SERIAL / CREATE
    # UNIQUE INDEX … WHERE syntax differs across dialects.
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS user_medals (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    medal_type VARCHAR(10) NOT NULL,
                    period_type VARCHAR(10) NOT NULL,
                    period_start DATE NOT NULL,
                    mix_id INTEGER REFERENCES mixes(id),
                    likes_count INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.exec_driver_sql(
                """
                ALTER TABLE user_medals
                ADD COLUMN IF NOT EXISTS likes_count INTEGER NOT NULL DEFAULT 0
                """
            )
            conn.exec_driver_sql(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_user_medals_user_period_medal
                ON user_medals (user_id, period_type, period_start, medal_type)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_user_medals_user_id
                ON user_medals (user_id)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_user_medals_period_start
                ON user_medals (period_start)
                """
            )

    # MARK: lounge_subscriptions — per-topic push subscription table (2026-05-25)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS lounge_subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    brand_id VARCHAR(128) NOT NULL,
                    topic_events BOOLEAN NOT NULL DEFAULT TRUE,
                    topic_new_mix BOOLEAN NOT NULL DEFAULT TRUE,
                    topic_discounts BOOLEAN NOT NULL DEFAULT TRUE,
                    topic_news BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_user_brand_sub UNIQUE (user_id, brand_id)
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_lounge_subscriptions_user_id
                ON lounge_subscriptions (user_id)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_lounge_subscriptions_brand_id
                ON lounge_subscriptions (brand_id)
                """
            )

    # MARK: lounge_loyalty_programs — per-venue configurable loyalty (2026-05-25)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS lounge_loyalty_programs (
                    id SERIAL PRIMARY KEY,
                    brand_id VARCHAR(128) NOT NULL UNIQUE,
                    mode VARCHAR(32) NOT NULL DEFAULT 'percent_of_bill',
                    bill_percent INTEGER NOT NULL DEFAULT 5,
                    first_visit_bonus INTEGER NOT NULL DEFAULT 0,
                    per_visit_bonus INTEGER NOT NULL DEFAULT 0,
                    referral_bonus INTEGER NOT NULL DEFAULT 0,
                    birthday_multiplier INTEGER NOT NULL DEFAULT 2,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            # Seed для secret_yauza — сохраняем исторические fixed-правила
            conn.exec_driver_sql(
                """
                INSERT INTO lounge_loyalty_programs
                    (brand_id, mode, first_visit_bonus, per_visit_bonus,
                     referral_bonus, birthday_multiplier, bill_percent)
                VALUES ('secret_yauza', 'fixed', 1000, 50, 200, 2, 0)
                ON CONFLICT (brand_id) DO NOTHING
                """
            )

    # MARK: lounge_promos — static/recurring promotional offers (2026-05-26)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS lounge_promos (
                    id SERIAL PRIMARY KEY,
                    brand_id VARCHAR(128) NOT NULL,
                    title VARCHAR(256) NOT NULL,
                    description TEXT,
                    discount_percent INTEGER,
                    discount_text VARCHAR(64),
                    icon_name VARCHAR(64),
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_lounge_promos_brand_id
                ON lounge_promos (brand_id)
                """
            )
            # Unique constraint on (brand_id, title) — makes seed idempotent
            # across gunicorn workers and restarts.
            conn.exec_driver_sql(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_lounge_promos_brand_title
                ON lounge_promos (brand_id, title)
                """
            )
            # Seed — Garden Lounge 3 promos from design
            # Note: %% because exec_driver_sql uses % as param placeholder
            conn.exec_driver_sql(
                """
                INSERT INTO lounge_promos
                    (brand_id, title, description, discount_percent, discount_text,
                     icon_name, sort_order, active)
                VALUES
                  ('garden_lounge_korolev',
                   'Счастливые часы',
                   'Посетите заведение в будни до 18:00 и получите привилегию -25%%.',
                   25, '-25%%', 'clock.fill', 0, TRUE),
                  ('garden_lounge_korolev',
                   '-10%% за отзыв',
                   'Дарим скидку 10%% за отзыв — нам важно ваше мнение и мы хотим становиться лучше.',
                   10, '-10%%', 'star.fill', 1, TRUE),
                  ('garden_lounge_korolev',
                   '-15%% в день рождения',
                   'Дарим скидку 15%% в ваш День рождения. Предложение действует 7 дней до и 7 дней после вашего Дня рождения.',
                   15, '-15%%', 'gift.fill', 2, TRUE)
                ON CONFLICT (brand_id, title) DO NOTHING
                """
            )

    # MARK: lounge_visits — CRM visit ledger (2026-05-26)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS lounge_visits (
                    id SERIAL PRIMARY KEY,
                    brand_id VARCHAR(128) NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    bill_amount INTEGER NOT NULL DEFAULT 0,
                    bonus_awarded INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_lounge_visits_brand_created
                ON lounge_visits (brand_id, created_at DESC)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_lounge_visits_brand_user
                ON lounge_visits (brand_id, user_id)
                """
            )
            conn.exec_driver_sql(
                """
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS share_flavors BOOLEAN NOT NULL DEFAULT TRUE
                """
            )

    # MARK: lounge_guest_loyalty.bonus_balance — per-lounge bonus wallet (2026-05-26)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                ALTER TABLE lounge_guest_loyalties
                ADD COLUMN IF NOT EXISTS bonus_balance INTEGER NOT NULL DEFAULT 0
                """
            )
            # Backfill: approximate historical balance as visit_count * 50 pts.
            # Only touches rows where bonus_balance is still 0 and guest has visits.
            # Safe to re-run: condition "bonus_balance = 0 AND visit_count > 0"
            # prevents overwriting rows already updated by the new logic.
            conn.exec_driver_sql(
                """
                UPDATE lounge_guest_loyalties
                SET bonus_balance = visit_count * 50
                WHERE bonus_balance = 0 AND visit_count > 0
                """
            )
            # Юзер: «регуляры/гости не показываются а они есть».
            # До коммита 0431d67 CRM-таблицы lounge_visits ещё не было,
            # checkin писал только в lounge_guest_loyalties. Backfill:
            # для каждого гостя с visit_count > 0 создаём минимум одну
            # синтетическую lounge_visits-запись (visit_count раз, чтобы
            # GROUP BY count(*) дал правильное число регуляров), если
            # уже нет совсем своих записей для пары brand_id+user_id.
            conn.exec_driver_sql(
                """
                INSERT INTO lounge_visits (brand_id, user_id, bill_amount, bonus_awarded, created_at)
                SELECT lgl.brand_id, lgl.user_id, 0, 0,
                       COALESCE(lgl.last_visit_at, NOW())
                FROM lounge_guest_loyalties lgl
                WHERE lgl.visit_count > 0
                  AND NOT EXISTS (
                    SELECT 1 FROM lounge_visits lv
                    WHERE lv.brand_id = lgl.brand_id AND lv.user_id = lgl.user_id
                  )
                """
            )

    # MARK: bonus_redemptions — owner-initiated bonus write-off (2026-05-26)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS bonus_redemptions (
                    id SERIAL PRIMARY KEY,
                    brand_id VARCHAR(128) NOT NULL,
                    guest_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    owner_user_id INTEGER NOT NULL REFERENCES users(id),
                    amount_rub INTEGER NOT NULL,
                    bonus_points INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    note VARCHAR(256),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_bonus_redemptions_brand_id
                ON bonus_redemptions (brand_id)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_bonus_redemptions_guest_user_id
                ON bonus_redemptions (guest_user_id)
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_bonus_redemptions_brand_created
                ON bonus_redemptions (brand_id, created_at DESC)
                """
            )

    # MARK: lounge_promoted_slots — featured promo placements (2026-05-26)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS lounge_promoted_slots (
                    id SERIAL PRIMARY KEY,
                    brand_id VARCHAR(128) NOT NULL UNIQUE,
                    starts_at TIMESTAMPTZ NOT NULL,
                    ends_at TIMESTAMPTZ NOT NULL,
                    region VARCHAR(64),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_lounge_promoted_slots_brand_id
                ON lounge_promoted_slots (brand_id)
                """
            )
            # Seed: garden_lounge_korolev promoted for 7 days from now, region=moscow
            conn.exec_driver_sql(
                """
                INSERT INTO lounge_promoted_slots (brand_id, starts_at, ends_at, region)
                VALUES (
                    'garden_lounge_korolev',
                    NOW(),
                    NOW() + INTERVAL '7 days',
                    'moscow'
                )
                ON CONFLICT (brand_id) DO NOTHING
                """
            )

    # MARK: lounge_admin_meta — admin CRM tier + badges (2026-05-26)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS lounge_admin_meta (
                    id SERIAL PRIMARY KEY,
                    brand_id VARCHAR(128) NOT NULL UNIQUE,
                    tier VARCHAR(32) NOT NULL DEFAULT 'start',
                    badges JSONB NOT NULL DEFAULT '[]',
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_lounge_admin_meta_brand_id
                ON lounge_admin_meta (brand_id)
                """
            )
            # Seed: garden_lounge_korolev as partner with verified + mix_partner + featured
            conn.exec_driver_sql(
                """
                INSERT INTO lounge_admin_meta (brand_id, tier, badges)
                VALUES ('garden_lounge_korolev', 'partner', '["verified","mix_partner","featured"]')
                ON CONFLICT (brand_id) DO NOTHING
                """
            )

    # MARK: lounge_billing_subscriptions — billing/subscription table (Sprint 1, 2026-05-27)
    # Wrapped in try/except because multiple gunicorn workers run startup() concurrently;
    # CREATE TABLE IF NOT EXISTS can race and raise UniqueViolation on pg_type_typname_nsp_index.
    if engine.dialect.name == "postgresql":
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    """
                    CREATE TABLE IF NOT EXISTS lounge_billing_subscriptions (
                        id SERIAL PRIMARY KEY,
                        brand_id VARCHAR(128) NOT NULL,
                        tier VARCHAR(32) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        started_at TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        payment_method VARCHAR(64),
                        external_id VARCHAR(256),
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
                conn.exec_driver_sql(
                    """
                    CREATE INDEX IF NOT EXISTS idx_lounge_billing_sub_brand
                    ON lounge_billing_subscriptions(brand_id)
                    """
                )
                conn.exec_driver_sql(
                    """
                    CREATE INDEX IF NOT EXISTS idx_lounge_billing_sub_expires
                    ON lounge_billing_subscriptions(expires_at)
                    """
                )
                # Idempotent trial grant for garden_lounge_korolev — 90-day Pro trial
                conn.exec_driver_sql(
                    """
                    INSERT INTO lounge_billing_subscriptions
                        (brand_id, tier, status, started_at, expires_at, payment_method, created_at)
                    SELECT
                        'garden_lounge_korolev',
                        'pro',
                        'trialing',
                        NOW(),
                        NOW() + INTERVAL '90 days',
                        'trial',
                        NOW()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM lounge_billing_subscriptions
                        WHERE brand_id = 'garden_lounge_korolev'
                    )
                    """
                )
        except Exception as _billing_migration_exc:
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "lounge_billing_subscriptions migration skipped (likely race with another worker): %s",
                _billing_migration_exc,
            )

    # MARK: featured_slots — paid featured placements (2026-05-27)
    if engine.dialect.name == "postgresql":
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    """
                    CREATE TABLE IF NOT EXISTS featured_slots (
                        id SERIAL PRIMARY KEY,
                        brand_id VARCHAR(128) NOT NULL,
                        slot_type VARCHAR(32) NOT NULL,
                        city VARCHAR(64),
                        starts_at TIMESTAMP NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        price_paid INTEGER NOT NULL DEFAULT 0,
                        status VARCHAR(32) NOT NULL DEFAULT 'active',
                        payment_method VARCHAR(64),
                        created_by_admin BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
                conn.exec_driver_sql(
                    """
                    CREATE INDEX IF NOT EXISTS idx_featured_slots_active
                    ON featured_slots(status, expires_at)
                    WHERE status='active'
                    """
                )
                conn.exec_driver_sql(
                    """
                    CREATE INDEX IF NOT EXISTS idx_featured_slots_city
                    ON featured_slots(city, slot_type)
                    WHERE status='active'
                    """
                )
                # Idempotent seed: garden_lounge_korolev as hero for 7 days
                conn.exec_driver_sql(
                    """
                    INSERT INTO featured_slots
                        (brand_id, slot_type, city, starts_at, expires_at,
                         price_paid, status, payment_method, created_by_admin, created_at)
                    SELECT
                        'garden_lounge_korolev', 'hero', 'general',
                        NOW(), NOW() + INTERVAL '7 days',
                        0, 'active', 'trial', TRUE, NOW()
                    WHERE NOT EXISTS (
                        SELECT 1 FROM featured_slots
                        WHERE brand_id = 'garden_lounge_korolev' AND status = 'active'
                    )
                    """
                )
        except Exception as _featured_migration_exc:
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "featured_slots migration skipped (likely race with another worker): %s",
                _featured_migration_exc,
            )

    # MARK: Hot-path FK indexes (perf audit 2026-05-26)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for _ix_sql in (
                "CREATE INDEX IF NOT EXISTS ix_mixes_author_id ON mixes(author_id)",
                "CREATE INDEX IF NOT EXISTS ix_mix_ingredients_mix_id ON mix_ingredients(mix_id)",
                "CREATE INDEX IF NOT EXISTS ix_comments_mix_id ON comments(mix_id)",
                "CREATE INDEX IF NOT EXISTS ix_comments_user_id ON comments(user_id)",
                "CREATE INDEX IF NOT EXISTS ix_monthly_votes_mix_id ON monthly_votes(mix_id)",
                "CREATE INDEX IF NOT EXISTS ix_monthly_votes_user_id ON monthly_votes(user_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_activities_user_id ON user_activities(user_id)",
                "CREATE INDEX IF NOT EXISTS ix_bowl_heat_runs_user_id ON bowl_heat_runs(user_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_follows_follower_id ON user_follows(follower_id)",
                "CREATE INDEX IF NOT EXISTS ix_user_follows_following_id ON user_follows(following_id)",
            ):
                conn.exec_driver_sql(_ix_sql)

    # MARK: APScheduler — weekly + monthly medal grant.
    # We start a per-worker BackgroundScheduler. With multiple gunicorn
    # workers the unique constraint on user_medals guarantees idempotency:
    # only the first worker's INSERTs succeed, the rest hit IntegrityError
    # and are skipped silently.
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from app.services import leaderboard as _leaderboard_module

        _medal_scheduler = BackgroundScheduler(timezone="Europe/Moscow")

        def _run_weekly_grant():
            session = SessionLocal()
            try:
                _leaderboard_module.grant_medals_for_period(session, "week")
            except Exception as exc:  # pragma: no cover — defensive log
                import logging as _lg
                _lg.getLogger(__name__).exception("weekly medal grant failed: %s", exc)
            finally:
                session.close()

        def _run_monthly_grant():
            session = SessionLocal()
            try:
                _leaderboard_module.grant_medals_for_period(session, "month")
            except Exception as exc:  # pragma: no cover
                import logging as _lg
                _lg.getLogger(__name__).exception("monthly medal grant failed: %s", exc)
            finally:
                session.close()

        _medal_scheduler.add_job(
            _run_weekly_grant,
            CronTrigger(day_of_week="mon", hour=0, minute=0, timezone="Europe/Moscow"),
            id="leaderboard_weekly_medal_grant",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        _medal_scheduler.add_job(
            _run_monthly_grant,
            CronTrigger(day=1, hour=0, minute=0, timezone="Europe/Moscow"),
            id="leaderboard_monthly_medal_grant",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        _medal_scheduler.start()
        # Stash on app.state so tests / future shutdown hook can grab it.
        app.state.medal_scheduler = _medal_scheduler
    except Exception as exc:  # pragma: no cover — never block app startup
        import logging as _lg
        _lg.getLogger(__name__).warning(
            "leaderboard scheduler not started: %s", exc
        )

    # MARK: lounge_catalog — server-driven lounge catalog (2026-05-28)
    # Allows new lounges to appear in iOS app without a rebuild.
    if engine.dialect.name == "postgresql":
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    """
                    CREATE TABLE IF NOT EXISTS lounge_catalog (
                        brand_id TEXT PRIMARY KEY,
                        profile_json JSONB NOT NULL,
                        is_active BOOLEAN NOT NULL DEFAULT true,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                conn.exec_driver_sql(
                    """
                    CREATE INDEX IF NOT EXISTS idx_lounge_catalog_active
                    ON lounge_catalog (is_active)
                    WHERE is_active = true
                    """
                )
                # Seed: myata_platinum
                _myata_json = json.dumps({
                    "brand_id": "myata_platinum",
                    "title": "Мята Платинум Событие",
                    "category": "lounge",
                    "accent_hex": "A8F55F",
                    "secondary_hex": "15220F",
                    "badge": "Network lounge",
                    "tagline": "Африканский лаундж-бар Мяты в ЖК «Событие»: джунгли посреди Москвы, кухня comfort food, авторские коктейли и loyalty-логика сети.",
                    "summary": "Мята Платинум Событие — лаундж-бар в африканском стиле в ЖК «Событие»: двухметровые скульптуры, четырёхметровые пальмы и панорамные окна. Кухня comfort food с африканскими нотками, авторские коктейли. На уровне продукта это сильный пример сетевого lounge с понятной loyalty-системой бренда.",
                    "signature": "Сильная сторона места: атмосферный африканский lounge-формат с сервисом и встроенной loyalty-логикой Мяты.",
                    "heritage": "В приложении Мята Платинум Событие показывает, как работает сетевой lounge со своей системой возврата и бонусов.",
                    "best_for": "Подходит для rail'ов `с loyalty`, `сеть`, `атмосфера`, `вечеринки` и как пример non-HookahPlace места в Москве.",
                    "lines": ["Африканский интерьер", "Кухня comfort food", "Авторские коктейли", "Панорамные окна", "VIP-зоны", "Мята Loyalty"],
                    "highlights": ["Loyalty", "Атмосфера", "Сетевой lounge"],
                    "aliases": ["мята событие", "мята платинум событие", "myata platinum sobytie", "мята platinum событие", "myata_platinum", "мята жк событие"],
                    "hero_symbol": "leaf.fill",
                    "logo_image_url": None,
                    "hero_image_url": "http://188.253.19.166:8000/static/lounges/myata_platinum_cover.jpg",
                    "avatar_url": None,
                    "cover_url": None,
                    "official_authors": ["myata_platinum", "Мята Платинум Событие", "Myata Platinum Sobytie", "Мята Событие"],
                    "venue_address": "Москва, ул. Василия Ланового, 5 (ЖК «Событие»)",
                    "nearest_metro": "Минская",
                    "venue_latitude": 55.7180,
                    "venue_longitude": 37.4905,
                    "venue_hours": "Вс-Чт 11:00-02:00 · Пт-Сб 11:00-04:00",
                    "venue_price": "ср. чек ~2 200 ₽",
                    "venue_format": "Африканский лаунж · кухня · коктейли",
                    "venue_phone": "+7 916 666-45-11",
                    "venue_booking_url": "https://myatasobytiye.ru",
                    "venue_menu_url": "https://myatasobytiye.ru",
                    "venue_loyalty_title": "Мята Loyalty",
                    "venue_loyalty_summary": "Сетевой loyalty-слой Мяты: welcome-баллы, кешбэк, рост уровня и возможность оплачивать часть счёта бонусами.",
                    "articles": [
                        {
                            "id": "myata_platinum_event",
                            "title": "Happy Hours 17–19",
                            "subtitle": "Каждый будний день: кальян + чай по специальной цене до вечернего наплыва.",
                            "tag": "Акции",
                            "image_url": "https://sf.imcsoft.ru/image/1122/109/109_1766747075587dbe304104532a90610e941321f6c3-optimization.jpg"
                        },
                        {
                            "id": "myata_platinum_loyalty",
                            "title": "Loyalty-система сети Мята",
                            "subtitle": "Баллы, кешбэк и рост уровня делают это место удобным кейсом для вкладки `Места`.",
                            "tag": "Новости",
                            "image_url": "https://sf.imcsoft.ru/image/1104/309/309_1692020978514c77ef6afffc1dae471d07ee09cd49.jpg"
                        }
                    ],
                    "menu_highlights": [
                        {
                            "id": "myata_platinum_africa",
                            "title": "Африканская атмосфера",
                            "subtitle": "Скульптуры, пальмы и панорамные окна — особенный вечерний сценарий.",
                            "icon_name": "leaf.fill"
                        },
                        {
                            "id": "myata_platinum_kitchen",
                            "title": "Кухня comfort food",
                            "subtitle": "Понятная, но интересная кухня с африканскими нотками.",
                            "icon_name": "fork.knife"
                        },
                        {
                            "id": "myata_platinum_loyalty",
                            "title": "Мята Loyalty",
                            "subtitle": "Привилегии и накопительная логика сети, понятная пользователю.",
                            "icon_name": "star.circle.fill"
                        }
                    ],
                    "service_cards": [
                        {
                            "id": "myata_platinum_open",
                            "title": "Открыть заведение",
                            "subtitle": "Официальная карточка lounge с бронью и услугами.",
                            "icon_name": "calendar.badge.plus",
                            "destination_url": "https://myatasobytiye.ru"
                        },
                        {
                            "id": "myata_platinum_menu",
                            "title": "Открыть карточку Мяты",
                            "subtitle": "Меню, новости и услуги заведения.",
                            "icon_name": "menucard.fill",
                            "destination_url": "https://myatasobytiye.ru"
                        },
                        {
                            "id": "myata_platinum_call",
                            "title": "Позвонить",
                            "subtitle": "+7 916 666-45-11",
                            "icon_name": "phone.fill",
                            "destination_url": "tel://79166664511"
                        }
                    ]
                }, ensure_ascii=False)
                conn.exec_driver_sql(
                    """
                    INSERT INTO lounge_catalog (brand_id, profile_json, is_active, updated_at)
                    VALUES ('myata_platinum', %s::jsonb, true, now())
                    ON CONFLICT (brand_id) DO NOTHING
                    """,
                    (_myata_json,),
                )
        except Exception as _catalog_exc:
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "lounge_catalog migration skipped: %s", _catalog_exc
            )

    # MARK: lounge_owner_credentials — plaintext creds for CRM (2026-05-28)
    if engine.dialect.name == "postgresql":
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    """
                    CREATE TABLE IF NOT EXISTS lounge_owner_credentials (
                        brand_id TEXT PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        email TEXT,
                        username TEXT,
                        password_plain TEXT,
                        updated_at TIMESTAMPTZ DEFAULT now()
                    )
                    """
                )
        except Exception as _loc_exc:
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "lounge_owner_credentials migration skipped: %s", _loc_exc
            )

    # MARK: backfill lounge owner accounts (2026-05-28)
    # Runs on every startup but is idempotent — skips brands that already have a creds row.
    if engine.dialect.name == "postgresql":
        _bfdb = SessionLocal()
        try:
            # 1. myata_platinum — hardcoded known credentials, user_id=92
            _myata_existing = _bfdb.execute(
                sa_text("SELECT brand_id FROM lounge_owner_credentials WHERE brand_id = 'myata_platinum'")
            ).first()
            if not _myata_existing:
                _bfdb.execute(
                    sa_text(
                        """
                        INSERT INTO lounge_owner_credentials (brand_id, user_id, email, username, password_plain, updated_at)
                        VALUES ('myata_platinum', 92, 'myata.platinum@ember.app', 'myata_platinum', 'MyataEvent2026', now())
                        ON CONFLICT (brand_id) DO NOTHING
                        """
                    )
                )
                _bfdb.commit()

            # 2. All other lounges in lounge_catalog that have no creds row yet
            _all_brands = _bfdb.execute(
                sa_text("SELECT brand_id FROM lounge_catalog WHERE is_active = true")
            ).fetchall()
            for (_bid,) in _all_brands:
                if _bid == "myata_platinum":
                    continue
                _has_creds = _bfdb.execute(
                    sa_text("SELECT brand_id FROM lounge_owner_credentials WHERE brand_id = :b"),
                    {"b": _bid},
                ).first()
                if not _has_creds:
                    ensure_lounge_owner(_bid, _bfdb)
        except Exception as _bf_exc:
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "lounge owner backfill skipped: %s", _bf_exc
            )
        finally:
            _bfdb.close()

# -------------------------------------------------------------------
# LEGAL — Privacy Policy & Terms of Use (152-FZ / App Store compliance)
# No auth required. Served as HTML for WKWebView / Safari.
# -------------------------------------------------------------------
@app.get("/legal/privacy", response_class=HTMLResponse, tags=["legal"])
def get_privacy_policy():
    _legal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "legal", "privacy.html")
    with open(_legal_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.get("/legal/terms", response_class=HTMLResponse, tags=["legal"])
def get_terms_of_use():
    _legal_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "legal", "terms.html")
    with open(_legal_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


# -------------------------------------------------------------------
# AUTH
# -------------------------------------------------------------------
@app.post("/signup", response_model=LoginResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    # Pre-check на дубликаты — иначе db.commit падает IntegrityError → 500
    # → iOS показывает generic «На сервере что-то сломалось». Юзер не понимает
    # что именно надо исправить.
    email_norm = (payload.email or "").strip().lower()
    username_norm = (payload.username or "").strip()

    # 152-FZ / App Store: user must explicitly accept Terms of Use and Privacy Policy
    if not payload.accepted_terms:
        raise HTTPException(
            400,
            "Необходимо принять Условия использования и Политику конфиденциальности"
        )

    if not email_norm:
        raise HTTPException(400, "Введи email — без него регистрация невозможна.")
    if len(payload.password or "") < 6:
        raise HTTPException(400, "Пароль должен быть минимум 6 символов.")
    if username_norm and len(username_norm) < 3:
        raise HTTPException(400, "Username должен быть минимум 3 символа.")
    if username_norm and not re.fullmatch(r"[a-zA-Z0-9_]+", username_norm):
        raise HTTPException(400, "Username может содержать только латиницу, цифры и _.")

    existing_email = db.query(User).filter(User.email == email_norm).first()
    if existing_email:
        raise HTTPException(400, "Этот email уже зарегистрирован. Войди или восстанови пароль.")

    if username_norm:
        existing_username = db.query(User).filter(User.username == username_norm).first()
        if existing_username:
            raise HTTPException(400, f"Username «{username_norm}» уже занят. Выбери другой.")

    user = User(
        email=email_norm,
        username=username_norm or None,
        password_hash=hash_password(payload.password),
        is_admin=False,
        accepted_terms_at=datetime.utcnow()  # 152-FZ: record consent timestamp
    )
    if user_matches_admin_allowlist(user):
        user.is_admin = True
    db.add(user)
    db.flush()
    track_daily_login(user, db)

    # ON-8: Referral reward — 200 ugolki to the referrer on successful signup.
    # Юзер: «garden_lounge_korolev приглашал других и код вставлял» но БД
    # показывала 0 referral_reward. ReferralView в iOS формирует код как
    # «HOOKA3-USERNAME», юзер вставлял его целиком → backend искал по
    # точному username → ничего не находил → silent skip.
    # Нормализуем: lowercase + strip префикс «HOOKA3-» если есть.
    if payload.referrer_code:
        normalized_code = payload.referrer_code.strip()
        if normalized_code.upper().startswith("HOOKA3-"):
            normalized_code = normalized_code[7:]
        referrer = (
            db.query(User)
            .filter(func.lower(User.username) == normalized_code.lower())
            .first()
        )
        if referrer and referrer.id != user.id:
            try:
                record_progress_event(
                    user=referrer,
                    db=db,
                    event_type="referral_reward",
                    title="Реферал",
                    description=f"{user.username or user.email} зарегистрировался по твоей ссылке",
                    points_delta=200,
                    rating_delta=0,
                )
                # Юзер: «не пришёл push что по моей ссылке создали аккаунт».
                # Шлём push реферреру синхронно — внутри try/except чтобы
                # не блокировать signup при сбое APNs.
                try:
                    from app.push import send_push_fanout_async
                    import asyncio as _asyncio
                    invited_name = user.username or user.email or "новый юзер"
                    _asyncio.run(send_push_fanout_async(
                        db,
                        [referrer.id],
                        "🎉 У тебя новый реферал!",
                        f"{invited_name} зарегистрировался по твоей ссылке. +200 угольков на баланс.",
                        payload={"type": "referral", "new_user_id": user.id},
                    ))
                except Exception as push_e:
                    print(f"[referral] push failed for {referrer.id}: {push_e}")
            except Exception as e:
                print(f"[referral] reward failed for {referrer.id}: {e}")

    db.commit()
    db.refresh(user)

    # Issue refresh token for new clients
    raw_rt, rt_hash, rt_expires = create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=rt_hash,
        issued_at=datetime.utcnow(),
        expires_at=rt_expires,
    ))
    db.commit()

    return LoginResponse(
        user_id=user.id,
        token=create_access_token({"sub": str(user.id)}),
        username=user.username,
        refresh_token=raw_rt,
        access_expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    # Принимаем email ИЛИ username (для lounge-owner аккаунтов вроде
    # gallery_secret_lounge у которых email = служебный).
    identifier = (payload.email or "").strip()
    user = (
        db.query(User)
        .filter((User.email == identifier) | (User.username == identifier))
        .first()
    )

    if not user or not verify_password(
        payload.password,
        user.password_hash
    ):
        raise HTTPException(400, "Invalid credentials")

    if user.is_banned:
        raise HTTPException(403, user.ban_reason or "Account banned")

    # Opportunistic SHA-256 → bcrypt миграция. Юзер ничего не замечает,
    # на следующем логине пароль будет уже в bcrypt.
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    track_daily_login(user, db)

    # Issue refresh token
    raw_rt, rt_hash, rt_expires = create_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=rt_hash,
        issued_at=datetime.utcnow(),
        expires_at=rt_expires,
    ))
    db.commit()

    return LoginResponse(
        user_id=user.id,
        token=create_access_token({"sub": str(user.id)}),
        username=user.username,
        refresh_token=raw_rt,
        access_expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# -------------------------------------------------------------------
# AUTH — refresh + logout
# -------------------------------------------------------------------

@app.post("/auth/refresh", response_model=TokenRefreshResponse)
def auth_refresh(
    payload: TokenRefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Rotate a refresh token. Old token is revoked immediately.
    Returns new access_token + new refresh_token.

    Backward-compat: old long-lived access tokens (7-day exp) issued
    before this feature was deployed keep working until they expire.
    """
    incoming_hash = hash_refresh_token(payload.refresh_token)
    row = db.query(RefreshToken).filter(
        RefreshToken.token_hash == incoming_hash
    ).first()

    if not row:
        raise HTTPException(401, "Invalid refresh token")
    if row.revoked_at is not None:
        raise HTTPException(401, "Refresh token revoked")
    if row.expires_at < datetime.utcnow():
        raise HTTPException(401, "Refresh token expired")

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user or user.is_banned or user.is_deleted:
        raise HTTPException(401, "Account unavailable")

    # Revoke old token (rotation)
    row.revoked_at = datetime.utcnow()

    # Issue new pair
    raw_rt, rt_hash, rt_expires = create_refresh_token()
    ua = request.headers.get("user-agent", "")[:512]
    ip = request.client.host if request.client else None
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=rt_hash,
        issued_at=datetime.utcnow(),
        expires_at=rt_expires,
        user_agent=ua,
        ip=ip,
    ))
    db.commit()

    return TokenRefreshResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=raw_rt,
        access_expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/auth/logout", response_model=StatusOut)
def auth_logout(
    payload: LogoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Invalidate a refresh token. If refresh_token is provided — revoke
    that specific session. Otherwise revoke all active sessions for the
    current user (full logout).
    """
    current_user = get_required_user(user)
    now = datetime.utcnow()

    if payload.refresh_token:
        incoming_hash = hash_refresh_token(payload.refresh_token)
        row = db.query(RefreshToken).filter(
            RefreshToken.token_hash == incoming_hash,
            RefreshToken.user_id == current_user.id,
        ).first()
        if row and row.revoked_at is None:
            row.revoked_at = now
    else:
        # Revoke all active sessions
        db.query(RefreshToken).filter(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        ).update({"revoked_at": now})

    db.commit()
    return StatusOut(status="ok")


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


# -------------------------------------------------------------------
# EVENTS / PROMOS
# -------------------------------------------------------------------
@app.get("/events", response_model=List[EventOut])
@limiter.limit("30/minute")
def list_events(
    request: Request,
    lounge_id: Optional[str] = Query(None),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Event)
    if lounge_id:
        q = q.filter(Event.lounge_id == lounge_id)
    rows = q.order_by(Event.starts_at.asc(), Event.created_at.desc()).all()
    current_user_id = user.id if user else None
    return [_event_to_out(event, current_user_id, db) for event in rows]


@app.get("/events/{event_id}", response_model=EventOut)
def get_event(
    event_id: str,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    return _event_to_out(event, user.id if user else None, db)


@app.post("/events", response_model=EventOut)
def create_event(
    payload: EventIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = get_required_user(user)
    if payload.lounge_id:
        if not can_manage_brand(current_user, payload.lounge_id):
            raise HTTPException(403, "Business access required")
    elif not current_user.is_admin:
        raise HTTPException(403, "Admin only for non-lounge events")

    event = Event(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        title=payload.title.strip(),
        starts_at=payload.starts_at,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    _apply_event_payload(event, payload, current_user)
    event.created_at = datetime.utcnow()
    db.add(event)
    db.commit()
    db.refresh(event)

    # APNs: push гостям у которых есть хотя бы один чекин в этом лаунже
    # (LoungeGuestLoyalty — proxy «активный гость»).
    # Per-topic фильтрацию (topic_events) backend применит в следующей итерации
    # когда iOS начнёт синхронизировать настройки через PUT /lounges/{id}/subscription.
    try:
        import asyncio as _asyncio
        from app.push import send_push_fanout_async
        guest_ids = db.query(LoungeGuestLoyalty.user_id).filter(
            LoungeGuestLoyalty.brand_id == event.lounge_id
        ).distinct().limit(5000).all() if event.lounge_id else []
        title = "Новый эвент"
        body = f"{event.title} — {event.starts_at.strftime('%d.%m %H:%M')}"
        push_payload = {
            "type": "event",
            "event_id": event.id,
            "lounge_id": event.lounge_id or "",
        }
        uid_list = [uid for (uid,) in guest_ids if uid != current_user.id]
        if uid_list:
            _asyncio.run(send_push_fanout_async(db, uid_list, title, body, payload=push_payload))
    except Exception as e:
        print(f"[push] event-create notify failed: {e}")

    return _event_to_out(event, current_user.id, db)


@app.patch("/events/{event_id}", response_model=EventOut)
def update_event(
    event_id: str,
    payload: EventIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = get_required_user(user)
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")

    managed_lounge_id = payload.lounge_id or event.lounge_id
    if managed_lounge_id:
        if not can_manage_brand(current_user, managed_lounge_id):
            raise HTTPException(403, "Business access required")
    elif not current_user.is_admin:
        raise HTTPException(403, "Admin only")

    _apply_event_payload(event, payload, current_user)
    db.commit()
    db.refresh(event)
    return _event_to_out(event, current_user.id, db)


@app.delete("/events/{event_id}", response_model=StatusOut)
def delete_event(
    event_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = get_required_user(user)
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    if event.lounge_id:
        if not can_manage_brand(current_user, event.lounge_id):
            raise HTTPException(403, "Business access required")
    elif not current_user.is_admin:
        raise HTTPException(403, "Admin only")
    db.delete(event)
    db.commit()
    return StatusOut(status="ok", message="Event deleted")


_EVENT_PHOTO_MAX_DIM = 1200   # max width/height in pixels
_EVENT_PHOTO_MAX_BYTES = 8 * 1024 * 1024  # 8 MB


@app.post("/events/photo", response_model=EventPhotoOut)
def upload_event_photo(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Upload an event cover photo (multipart JPEG).
    Any authenticated lounge owner (or admin) can upload.
    Image is resized to fit within 1200px on the longest side and saved as JPEG
    under /app/static/events/{uuid}.jpg.
    Returns {"url": "http://188.253.19.166:8000/static/events/{uuid}.jpg"}."""
    get_required_user(user)  # must be logged in

    raw = file.file.read()
    if len(raw) > _EVENT_PHOTO_MAX_BYTES:
        raise HTTPException(413, "Image too large (max 8 MB)")

    try:
        from PIL import Image as _PIL_Image
        from io import BytesIO as _BytesIO
    except Exception as e:
        raise HTTPException(500, f"Image processing unavailable: {e}")

    try:
        img = _PIL_Image.open(_BytesIO(raw))
        img.load()
    except Exception as e:
        raise HTTPException(400, f"Cannot decode image: {e}")

    # Resize to fit within _EVENT_PHOTO_MAX_DIM on longest side (no upscale)
    w, h = img.size
    max_dim = _EVENT_PHOTO_MAX_DIM
    if w > max_dim or h > max_dim:
        ratio = min(max_dim / w, max_dim / h)
        img = img.resize((int(w * ratio), int(h * ratio)), _PIL_Image.LANCZOS)

    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    from io import BytesIO as _BytesIO2
    buf = _BytesIO2()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    image_bytes = buf.getvalue()

    fname = f"{uuid.uuid4().hex}.jpg"
    from app.services.storage import get_storage as _get_storage
    storage = _get_storage()
    key = f"events/{fname}"
    url = storage.upload(key, image_bytes, "image/jpeg")

    if not url.startswith("http"):
        url = f"http://188.253.19.166:8000{url}"

    return EventPhotoOut(url=url)


@app.post("/events/{event_id}/rsvp", response_model=EventRSVPOut)
def rsvp_event(
    event_id: str,
    payload: EventRSVPIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = get_required_user(user)
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    row = db.query(EventRSVP).filter(
        EventRSVP.event_id == event_id,
        EventRSVP.user_id == current_user.id,
    ).first()
    if row is None:
        row = EventRSVP(event_id=event_id, user_id=current_user.id)
        db.add(row)
    row.going = payload.going
    row.updated_at = datetime.utcnow()
    db.commit()
    going_count = db.query(EventRSVP).filter(
        EventRSVP.event_id == event_id,
        EventRSVP.going == True,  # noqa: E712
    ).count()
    return EventRSVPOut(status="ok", going=row.going, going_count=going_count)


# ===================================================================
# BLOCK: Featured Slots public feed (2026-05-27)
# NOTE: must be declared BEFORE /lounges/{brand_id}/... routes
# ===================================================================

@app.get(
    "/lounges/featured",
    response_model=FeaturedFeedOut,
    tags=["lounges"],
)
def get_featured_lounges(
    city: Optional[str] = Query(None, description="Город: msk | spb | general"),
    slot_type: Optional[str] = Query(None, description="Тип слота: hero | grid"),
    db: Session = Depends(get_db),
):
    """
    Публичный endpoint для iOS. Возвращает активные featured-слоты.
    hero — первый активный hero-слот для города (или general), max 1.
    grid — все активные grid-слоты для города (или general).
    """
    now = datetime.utcnow()

    base_q = db.query(FeaturedSlot).filter(
        FeaturedSlot.status == "active",
        FeaturedSlot.expires_at > now,
    )

    if city:
        base_q = base_q.filter(
            (FeaturedSlot.city == city) | (FeaturedSlot.city == "general")
        )

    def _to_out(r: FeaturedSlot) -> FeaturedSlotOut:
        remaining = max(0, (r.expires_at - now).days)
        return FeaturedSlotOut(
            id=r.id,
            brand_id=r.brand_id,
            slot_type=r.slot_type,
            city=r.city,
            starts_at=r.starts_at,
            expires_at=r.expires_at,
            price_paid=r.price_paid or 0,
            status=r.status,
            payment_method=r.payment_method,
            created_by_admin=r.created_by_admin or False,
            created_at=r.created_at,
            remaining_days=remaining,
        )

    hero_slot: Optional[FeaturedSlotOut] = None
    grid_slots: list = []

    if slot_type in (None, "hero"):
        hero_row = (
            base_q.filter(FeaturedSlot.slot_type == "hero")
            .order_by(FeaturedSlot.expires_at.desc())
            .first()
        )
        if hero_row:
            hero_slot = _to_out(hero_row)

    if slot_type in (None, "grid"):
        grid_rows = (
            base_q.filter(FeaturedSlot.slot_type == "grid")
            .order_by(FeaturedSlot.expires_at.desc())
            .all()
        )
        grid_slots = [_to_out(r) for r in grid_rows]

    return FeaturedFeedOut(hero=hero_slot, grid=grid_slots)


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
# LOUNGE PROMOS  (static / recurring offers, 2026-05-26)
# -------------------------------------------------------------------

@app.get("/lounges/{brand_id}/promos", response_model=LoungePromoListOut)
@limiter.limit("60/minute")
def list_lounge_promos(
    request: Request,
    brand_id: str,
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    """Public endpoint. Returns active promos by default.
    Pass ?include_inactive=true to see all (owner only)."""
    if include_inactive:
        # Only lounge owner/admin can see inactive promos
        current_user = get_required_user(user)
        if not can_manage_brand(current_user, brand_id):
            raise HTTPException(403, "Business access required")
        rows = (
            db.query(LoungePromo)
            .filter(LoungePromo.brand_id == brand_id)
            .order_by(LoungePromo.sort_order.asc(), LoungePromo.id.asc())
            .all()
        )
    else:
        rows = (
            db.query(LoungePromo)
            .filter(LoungePromo.brand_id == brand_id, LoungePromo.active.is_(True))
            .order_by(LoungePromo.sort_order.asc(), LoungePromo.id.asc())
            .all()
        )
    return LoungePromoListOut(
        items=[LoungePromoOut.from_orm(r) for r in rows],
        total=len(rows),
    )


@app.post("/lounges/{brand_id}/promos", response_model=LoungePromoOut, status_code=201)
@limiter.limit("60/minute")
def create_lounge_promo(
    request: Request,
    brand_id: str,
    payload: LoungePromoIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new promo for a lounge. Owner / admin only. Requires tier >= lite."""
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")
    # Feature gate: promos require lite or higher
    if not current_user.is_admin:
        require_tier(db, brand_id, "lite")

    promo = LoungePromo(
        brand_id=brand_id,
        title=payload.title.strip(),
        description=payload.description,
        discount_percent=payload.discount_percent,
        discount_text=payload.discount_text,
        icon_name=payload.icon_name,
        active=payload.active,
        sort_order=payload.sort_order,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return LoungePromoOut.from_orm(promo)


@app.patch("/promos/{promo_id}", response_model=LoungePromoOut)
@limiter.limit("60/minute")
def update_lounge_promo(
    request: Request,
    promo_id: int,
    payload: LoungePromoUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update promo fields. Only owner of the lounge that owns this promo. Requires tier >= lite."""
    current_user = get_required_user(user)
    promo = db.query(LoungePromo).filter(LoungePromo.id == promo_id).first()
    if not promo:
        raise HTTPException(404, "Promo not found")
    if not can_manage_brand(current_user, promo.brand_id):
        raise HTTPException(403, "Business access required")
    # Feature gate: promos require lite or higher
    if not current_user.is_admin:
        require_tier(db, promo.brand_id, "lite")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(promo, field, value)

    db.commit()
    db.refresh(promo)
    return LoungePromoOut.from_orm(promo)


@app.delete("/promos/{promo_id}", response_model=StatusOut)
@limiter.limit("60/minute")
def delete_lounge_promo(
    request: Request,
    promo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Hard delete a promo. Only owner of the lounge that owns this promo."""
    current_user = get_required_user(user)
    promo = db.query(LoungePromo).filter(LoungePromo.id == promo_id).first()
    if not promo:
        raise HTTPException(404, "Promo not found")
    if not can_manage_brand(current_user, promo.brand_id):
        raise HTTPException(403, "Business access required")

    db.delete(promo)
    db.commit()
    return StatusOut(status="ok", message=f"Promo {promo_id} deleted")


# -------------------------------------------------------------------
# LOUNGE LOYALTY PROGRAM  (per-venue configurable, 2026-05-25)
# -------------------------------------------------------------------

_LOYALTY_DEFAULTS = dict(
    mode="percent_of_bill",
    bill_percent=5,
    first_visit_bonus=0,
    per_visit_bonus=0,
    referral_bonus=0,
    birthday_multiplier=2,
)


def _loyalty_row_to_out(row: "LoungeLoyaltyProgram") -> LoungeLoyaltyProgramOut:
    return LoungeLoyaltyProgramOut(
        brand_id=row.brand_id,
        mode=row.mode,
        bill_percent=row.bill_percent,
        first_visit_bonus=row.first_visit_bonus,
        per_visit_bonus=row.per_visit_bonus,
        referral_bonus=row.referral_bonus,
        birthday_multiplier=row.birthday_multiplier,
    )


@app.get("/lounges/{brand_id}/loyalty", response_model=LoungeLoyaltyProgramOut)
@limiter.limit("60/minute")
def get_lounge_loyalty(request: Request, brand_id: str, db: Session = Depends(get_db)):
    """
    Public — no auth required.
    Returns the per-venue loyalty config. If no row exists, returns defaults
    without writing to the DB (lazy initialisation).
    """
    row = db.query(LoungeLoyaltyProgram).filter(
        LoungeLoyaltyProgram.brand_id == brand_id
    ).first()
    if row is None:
        return LoungeLoyaltyProgramOut(brand_id=brand_id, **_LOYALTY_DEFAULTS)
    return _loyalty_row_to_out(row)


@app.put("/lounges/{brand_id}/loyalty", response_model=LoungeLoyaltyProgramOut)
def update_lounge_loyalty(
    brand_id: str,
    payload: LoungeLoyaltyProgramIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Owner-only upsert for the per-venue loyalty config.
    Access: brand manager (can_manage_brand) or admin.
    Validates mode, bill_percent (0-100), bonuses (>=0), birthday_multiplier (1-10).
    Requires tier >= lite.
    """
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Only the lounge owner can edit loyalty settings")
    # Feature gate: loyalty customisation requires lite or higher
    if not current_user.is_admin:
        require_tier(db, brand_id, "lite")

    if payload.mode not in ("percent_of_bill", "fixed"):
        raise HTTPException(422, "mode must be 'percent_of_bill' or 'fixed'")
    if payload.bill_percent is not None and not (0 <= payload.bill_percent <= 100):
        raise HTTPException(422, "bill_percent must be 0-100")
    for field_name, val in [
        ("first_visit_bonus", payload.first_visit_bonus),
        ("per_visit_bonus", payload.per_visit_bonus),
        ("referral_bonus", payload.referral_bonus),
    ]:
        if val is not None and val < 0:
            raise HTTPException(422, f"{field_name} must be >= 0")
    if payload.birthday_multiplier is not None and not (1 <= payload.birthday_multiplier <= 10):
        raise HTTPException(422, "birthday_multiplier must be 1-10")

    row = db.query(LoungeLoyaltyProgram).filter(
        LoungeLoyaltyProgram.brand_id == brand_id
    ).first()
    if row is None:
        row = LoungeLoyaltyProgram(brand_id=brand_id, **_LOYALTY_DEFAULTS)
        db.add(row)

    row.mode = payload.mode
    if payload.bill_percent is not None:
        row.bill_percent = payload.bill_percent
    if payload.first_visit_bonus is not None:
        row.first_visit_bonus = payload.first_visit_bonus
    if payload.per_visit_bonus is not None:
        row.per_visit_bonus = payload.per_visit_bonus
    if payload.referral_bonus is not None:
        row.referral_bonus = payload.referral_bonus
    if payload.birthday_multiplier is not None:
        row.birthday_multiplier = payload.birthday_multiplier

    db.commit()
    db.refresh(row)
    return _loyalty_row_to_out(row)


@app.get("/lounges/loyalty/batch", response_model=List[LoungeLoyaltyProgramOut])
def get_lounge_loyalty_batch(
    ids: str,
    db: Session = Depends(get_db),
):
    """
    Public — no auth required.
    Batch fetch for multiple brand IDs (comma-separated).
    Returns list; missing brands get default values.
    Usage: GET /lounges/loyalty/batch?ids=secret_yauza,garden_lounge_korolev
    """
    brand_ids = [b.strip() for b in ids.split(",") if b.strip()][:50]
    rows = db.query(LoungeLoyaltyProgram).filter(
        LoungeLoyaltyProgram.brand_id.in_(brand_ids)
    ).all()
    row_map = {r.brand_id: _loyalty_row_to_out(r) for r in rows}
    result = []
    for bid in brand_ids:
        if bid in row_map:
            result.append(row_map[bid])
        else:
            result.append(LoungeLoyaltyProgramOut(brand_id=bid, **_LOYALTY_DEFAULTS))
    return result


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


# ── Lounge cover / avatar image upload (owner-only) ──────────────────────
# Pattern mirrors POST /me/master/avatar: iOS sends base64 JSON, we decode
# via Pillow, resize, save to /app/static/lounges/, then upsert the URL into
# lounge_assets.cover_url (or .avatar_url). LoungeAssetsOut is returned so the
# client can refresh its cache in a single round-trip.

import base64 as _b64_for_lounge

_LOUNGE_IMG_MAX_BYTES = 8 * 1024 * 1024  # 8 MB — covers are larger than avatars
_LOUNGE_COVER_SIZE = (1200, 675)         # 16:9 hero
_LOUNGE_AVATAR_SIZE = (400, 400)         # square logo


def _save_lounge_image(
    brand_id: str,
    raw: bytes,
    target_size: tuple[int, int],
    file_suffix: str,
    crop_mode: str,
) -> str:
    """Decode raw bytes, center-crop+resize to `target_size`, save as JPEG.
    `crop_mode` is "cover" (16:9 cover) or "square" (avatar). Returns a public
    URL like /static/lounges/<brand>_cover.jpg (relative — iOS resolves via
    BackendEnvironment.baseURL)."""
    if len(raw) > _LOUNGE_IMG_MAX_BYTES:
        raise HTTPException(413, "Image too large (max 8 MB)")
    try:
        from PIL import Image  # type: ignore
        from io import BytesIO
    except Exception as e:
        # Pillow is required — covers must be normalised so the UI doesn't
        # show stretched 4:3 photos in a 16:9 frame.
        raise HTTPException(500, f"Image processing unavailable: {e}")

    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception as e:
        raise HTTPException(400, f"Cannot decode image: {e}")

    # Center-crop to the target aspect ratio, then resize. This keeps faces /
    # signage centered and avoids the "крекий" stretched look.
    tw, th = target_size
    target_ratio = tw / th
    sw, sh = img.size
    src_ratio = sw / sh
    if src_ratio > target_ratio:
        # Source is wider — crop the sides.
        new_w = int(sh * target_ratio)
        x0 = (sw - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, sh))
    elif src_ratio < target_ratio:
        # Source is taller — crop top/bottom.
        new_h = int(sw / target_ratio)
        y0 = (sh - new_h) // 2
        img = img.crop((0, y0, sw, y0 + new_h))

    img = img.resize(target_size, Image.LANCZOS)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    # Safe filename — brand_id is owner-controlled but used as a path segment,
    # so strip anything that isn't alnum/dash/underscore.
    safe_brand = "".join(ch for ch in brand_id if ch.isalnum() or ch in ("-", "_"))
    if not safe_brand:
        raise HTTPException(400, "Invalid brand_id")
    fname = f"{safe_brand}_{file_suffix}.jpg"

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    image_bytes = buf.getvalue()

    # Upload via storage abstraction (local or S3 depending on ENV).
    from app.services.storage import get_storage as _get_storage
    storage = _get_storage()
    key = f"lounges/{fname}"
    url = storage.upload(key, image_bytes, "image/jpeg")

    # Append a cache-buster so iOS AsyncImage picks up the new file even when
    # the URL string is identical to the previous upload.
    ts = int(datetime.utcnow().timestamp())
    # For local storage the url is relative (/static/lounges/...), for S3 it's absolute.
    # The cache-buster is appended only for local (S3 objects are immutable by key).
    if not url.startswith("http"):
        url = f"{url}?v={ts}"
    return url


def _upload_lounge_image(
    brand_id: str,
    payload: LoungeImageUploadIn,
    field: str,                # "cover_url" or "avatar_url"
    target_size: tuple[int, int],
    file_suffix: str,           # "cover" or "avatar"
    user: User,
    db: Session,
) -> LoungeAssetsOut:
    """Shared handler for cover + avatar uploads. Auth + DB upsert + response."""
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    b64 = payload.payload_b64
    if not b64:
        raise HTTPException(400, "image_base64 (or data_base64) is required")
    try:
        raw = _b64_for_lounge.b64decode(b64, validate=False)
    except Exception:
        raise HTTPException(400, "Invalid base64 payload")

    url = _save_lounge_image(brand_id, raw, target_size, file_suffix, "cover")

    assets = db.query(LoungeAssets).filter(LoungeAssets.brand_id == brand_id).first()
    if assets is None:
        assets = LoungeAssets(brand_id=brand_id, photo_urls="[]", info_json="{}")
        db.add(assets)
    setattr(assets, field, url)
    assets.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assets)
    return _parse_lounge_assets(assets, brand_id)


@app.post("/lounges/{brand_id}/cover", response_model=LoungeAssetsOut)
def upload_lounge_cover(
    brand_id: str,
    payload: LoungeImageUploadIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a lounge cover photo. Owner / admin only. Image is center-cropped
    to 16:9 (1200×675) JPEG. Returns the updated LoungeAssetsOut so iOS can
    refresh `LoungeAssetsStore` in one round-trip."""
    return _upload_lounge_image(
        brand_id, payload, "cover_url", _LOUNGE_COVER_SIZE, "cover", user, db
    )


@app.post("/lounges/{brand_id}/avatar", response_model=LoungeAssetsOut)
def upload_lounge_avatar(
    brand_id: str,
    payload: LoungeImageUploadIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a lounge logo / avatar. Owner / admin only. Image is square-
    cropped to 400×400 JPEG."""
    return _upload_lounge_image(
        brand_id, payload, "avatar_url", _LOUNGE_AVATAR_SIZE, "avatar", user, db
    )


# ── Lounge Highlights (2026-05-28) ───────────────────────────────────────────
# Owner can configure up to 4 highlight cards (photo + title + subtitle).
# Cards are stored in lounge_catalog.profile_json["highlight_cards"].
# GET /catalog/lounges already returns the full profile_json, so iOS
# sees the cards automatically — no extra read endpoint needed.

_LOUNGE_HIGHLIGHT_SIZE = (800, 600)   # 4:3 card photo


@app.post("/lounges/{brand_id}/highlights/photo", response_model=LoungeHighlightPhotoOut)
def upload_highlight_photo(
    brand_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload a highlight card photo (multipart). Owner / admin only.
    Image is center-cropped to 800x600 JPEG and stored under
    /app/static/lounges/{brand_id}/hl_{timestamp}.jpg.
    Returns {"url": "http://188.253.19.166:8000/static/lounges/{brand_id}/hl_{ts}.jpg"}."""
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    raw = file.file.read()
    if len(raw) > _LOUNGE_IMG_MAX_BYTES:
        raise HTTPException(413, "Image too large (max 8 MB)")

    try:
        from PIL import Image as _PIL_Image
        from io import BytesIO as _BytesIO
    except Exception as e:
        raise HTTPException(500, f"Image processing unavailable: {e}")

    try:
        img = _PIL_Image.open(_BytesIO(raw))
        img.load()
    except Exception as e:
        raise HTTPException(400, f"Cannot decode image: {e}")

    tw, th = _LOUNGE_HIGHLIGHT_SIZE
    target_ratio = tw / th
    sw, sh = img.size
    src_ratio = sw / sh
    if src_ratio > target_ratio:
        new_w = int(sh * target_ratio)
        x0 = (sw - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, sh))
    elif src_ratio < target_ratio:
        new_h = int(sw / target_ratio)
        y0 = (sh - new_h) // 2
        img = img.crop((0, y0, sw, y0 + new_h))

    img = img.resize(_LOUNGE_HIGHLIGHT_SIZE, _PIL_Image.LANCZOS)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    safe_brand = "".join(ch for ch in brand_id if ch.isalnum() or ch in ("-", "_"))
    if not safe_brand:
        raise HTTPException(400, "Invalid brand_id")

    ts = int(datetime.utcnow().timestamp())
    fname = f"hl_{ts}.jpg"

    buf = _BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    image_bytes = buf.getvalue()

    from app.services.storage import get_storage as _get_storage
    storage = _get_storage()
    key = f"lounges/{safe_brand}/{fname}"
    url = storage.upload(key, image_bytes, "image/jpeg")

    # Ensure the URL is absolute for highlight cards (iOS uses it directly)
    if not url.startswith("http"):
        url = f"http://188.253.19.166:8000{url}"

    return LoungeHighlightPhotoOut(url=url)


@app.put("/lounges/{brand_id}/highlights", response_model=LoungeHighlightsOut)
def save_lounge_highlights(
    brand_id: str,
    payload: LoungeHighlightsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save up to 4 highlight cards for a lounge. Owner / admin only.
    Writes into lounge_catalog.profile_json['highlight_cards'] via jsonb_set.
    The existing GET /catalog/lounges returns the full profile_json so no
    additional read endpoint is needed."""
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    # Cap at 4 cards, assign deterministic ids hl_1..hl_4
    cards_in = payload.highlights[:4]
    cards_out = []
    for i, card in enumerate(cards_in, start=1):
        cards_out.append({
            "id": f"hl_{i}",
            "title": card.title.strip(),
            "subtitle": card.subtitle.strip(),
            "image_url": card.image_url.strip(),
        })

    cards_json = json.dumps(cards_out, ensure_ascii=False)

    # Upsert into lounge_catalog.profile_json using jsonb_set.
    # If the row doesn't exist yet, insert a minimal profile_json.
    existing = db.execute(
        sa_text("SELECT 1 FROM lounge_catalog WHERE brand_id = :bid"),
        {"bid": brand_id},
    ).fetchone()

    if existing:
        db.execute(
            sa_text(
                """
                UPDATE lounge_catalog
                SET profile_json = jsonb_set(
                    profile_json,
                    '{highlight_cards}',
                    CAST(:cards AS jsonb),
                    true
                ),
                updated_at = now()
                WHERE brand_id = :bid
                """
            ),
            {"cards": cards_json, "bid": brand_id},
        )
    else:
        minimal = json.dumps(
            {"brand_id": brand_id, "highlight_cards": cards_out},
            ensure_ascii=False,
        )
        db.execute(
            sa_text(
                """
                INSERT INTO lounge_catalog (brand_id, profile_json, is_active, updated_at)
                VALUES (:bid, CAST(:pj AS jsonb), true, now())
                """
            ),
            {"bid": brand_id, "pj": minimal},
        )

    db.commit()

    result = [HighlightCardOut(**c) for c in cards_out]
    return LoungeHighlightsOut(highlights=result)


@app.get("/lounges/{brand_id}/my-loyalty", response_model=LoungeMyLoyaltyOut)
@limiter.limit("60/minute")
def get_my_lounge_loyalty(
    request: Request,
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

    served_by_master = _resolve_checkin_master(payload.master_id, brand_id, db)
    served_by_master_id = served_by_master.id if served_by_master else None

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

    now_utc = datetime.utcnow()
    today = now_utc.date()
    # 4-hour cooldown between checkins per guest per venue (unlimited for dorfden user_id=1)
    is_unlimited_user = (guest_user.id == 1)
    if loyalty.last_visit_at and not is_unlimited_user:
        hours_since = (now_utc - loyalty.last_visit_at).total_seconds() / 3600
        if hours_since < 4:
            mins_left = int((4 - hours_since) * 60)
            raise HTTPException(429, f"Подожди 4 часа между чек-инами. Осталось {mins_left} мин.")
    # Legacy per-day limit (kept for safety, but 4h cooldown makes it redundant)
    if loyalty.last_visit_at and loyalty.last_visit_at.date() == today and not is_unlimited_user:
        cnt = loyalty.today_visit_count or 0
        if cnt >= 3:
            raise HTTPException(400, "Visit already registered today")
        loyalty.today_visit_count = cnt + 1
    else:
        loyalty.today_visit_count = (loyalty.today_visit_count or 0) + 1 if (loyalty.last_visit_at and loyalty.last_visit_at.date() == today) else 1

    # Determine first-visit status before incrementing
    is_first_visit = (loyalty.visit_count == 0)

    previous_tier = lounge_tier_for_visits(loyalty.visit_count)
    loyalty.visit_count += 1
    loyalty.last_visit_at = now_utc

    personalization = db.query(LoungeGuestPersonalization).filter(
        LoungeGuestPersonalization.brand_id == brand_id,
        LoungeGuestPersonalization.user_id == guest_user.id,
    ).first()
    program = get_lounge_program(brand_id, db)
    program_out = lounge_program_to_out(program, brand_id)

    # --- Bonus accrual via LoungeLoyaltyProgram ---
    loyalty_prog = db.query(LoungeLoyaltyProgram).filter(
        LoungeLoyaltyProgram.brand_id == brand_id
    ).first()
    lp_mode = loyalty_prog.mode if loyalty_prog else "percent_of_bill"
    lp_bill_percent = loyalty_prog.bill_percent if loyalty_prog else 5
    lp_first_bonus = loyalty_prog.first_visit_bonus if loyalty_prog else 0
    lp_per_bonus = loyalty_prog.per_visit_bonus if loyalty_prog else 0

    if lp_mode == "fixed":
        checkin_bonus = lp_first_bonus if is_first_visit else lp_per_bonus
    elif lp_mode == "percent_of_bill":
        if not payload.bill_amount or payload.bill_amount <= 0:
            raise HTTPException(400, "Сумма чека обязательна для этого заведения")
        # Юзер: «начисление бонусов или первое посещение не работает».
        # Раньше first_visit_bonus игнорировался в percent_of_bill режиме —
        # лаунж настраивал «+500 за первый визит, +5% за каждый», но
        # первый визит получал только процент. Теперь складываем процент
        # + first_visit_bonus (если это правда первый визит).
        base = int(payload.bill_amount * lp_bill_percent / 100)
        bonus_first = lp_first_bonus if is_first_visit else 0
        checkin_bonus = base + bonus_first
    else:
        checkin_bonus = 0

    if checkin_bonus > 0:
        # Бонусы лаунжа — per-lounge кошелёк, НЕ общие угольки.
        loyalty.bonus_balance = (loyalty.bonus_balance or 0) + checkin_bonus
        # Audit-trail в UserActivity: points_delta=0, чтобы НЕ менять общий
        # баланс угольков (UserProgress.points). Запись нужна только для
        # истории событий в ленте гостя.
        db.add(UserActivity(
            user_id=guest_user.id,
            event_type="lounge_checkin_bonus",
            title=f"Бонусы в {display_title_from_brand_id(brand_id)}",
            description=f"+{checkin_bonus} бонусов в этом заведении" + (
                f" (чек {int(payload.bill_amount)} ₽)" if lp_mode == "percent_of_bill" and payload.bill_amount else ""
            ),
            points_delta=0,   # не в общие угольки
            rating_delta=0,
        ))

    # Первый визит → 50 общих угольков как мотивация посещать новые заведения.
    if is_first_visit:
        record_progress_event(
            user=guest_user,
            db=db,
            event_type="lounge_first_visit",
            title=f"Первый визит в {display_title_from_brand_id(brand_id)}",
            description="+50 угольков за знакомство с новым заведением",
            points_delta=50,
            rating_delta=0,
        )
    # --- end bonus accrual ---
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
        master_id=served_by_master_id,
    )

    # CRM visit record — written every checkin for analytics
    visit_bill = int(payload.bill_amount) if payload.bill_amount and payload.bill_amount > 0 else 0
    db.add(LoungeVisit(
        brand_id=brand_id,
        user_id=guest_user.id,
        bill_amount=visit_bill,
        bonus_awarded=checkin_bonus,
    ))

    db.commit()

    loyalty_out = build_lounge_loyalty_out(brand_id, guest_user, db)
    is_level_up = previous_tier.title != loyalty_out.tier.title
    message = (
        f"Визит @{guest_user.username} в {display_title_from_brand_id(brand_id)} засчитан: "
        f"{loyalty_out.tier.title}, {loyalty_out.tier.discount_text} скидки."
    )

    # Bundle redemption — burn one included hookah if guest has active pack
    bundle_redeemed_out = _try_redeem_bundle_visit(db, guest_user.id, brand_id, served_by_master_id)


    # Create pending duel offer for guest
    from sqlalchemy import text as _sa_text
    db.execute(_sa_text("INSERT INTO pending_duel_offers (user_id, brand_id, discount_percent) VALUES (:uid, :bid, :disc)"), {"uid": guest_user.id, "bid": brand_id, "disc": loyalty_out.tier.discount_percent})
    db.commit()

    # Юзер: «при начислении бонусов кому назначили ничего не происходит».
    # Владелец сканит QR гостя → checkin начисляет баллы → но гость
    # ничего не видел. Шлём ему push сразу после commit.
    if checkin_bonus > 0:
        try:
            from app.push import send_push_fanout_async
            import asyncio as _asyncio_push
            venue_title = display_title_from_brand_id(brand_id)
            rub = checkin_bonus // 10
            body = (
                f"+{rub} ₽ ({checkin_bonus} баллов) в {venue_title}"
                if rub > 0
                else f"+{checkin_bonus} баллов в {venue_title}"
            )
            push_title = "🎉 Тебе начислили бонусы!" if is_first_visit else "🔥 +Бонусы за визит"
            _asyncio_push.run(send_push_fanout_async(
                db,
                [guest_user.id],
                push_title,
                body,
                payload={
                    "type": "checkin_bonus",
                    "brand_id": brand_id,
                    "bonus": checkin_bonus,
                    "is_first_visit": is_first_visit,
                },
            ))
        except Exception as push_e:
            print(f"[checkin] push failed for {guest_user.id}: {push_e}")

    return LoungeCheckinOut(
        guest=user_search_to_out(guest_user),
        loyalty=loyalty_out,
        is_level_up=is_level_up,
        message=message,
        bundle_redeemed=bundle_redeemed_out,
        bonus=checkin_bonus,
        is_first_visit=is_first_visit,
        mode=lp_mode,
    )


def _try_redeem_bundle_visit(
    db: Session,
    guest_user_id: int,
    brand_id: str,
    master_id: Optional[str] = None,
):
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
        master_id=master_id,
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
        master_id=master_id,
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


@app.get("/lounges/{brand_id}/busyness", response_model=LoungeBusynessOut)
def get_lounge_busyness(
    brand_id: str,
    db: Session = Depends(get_db),
):
    """
    Returns current busyness % for a lounge.

    Source priority:
      1. yandex_maps — manual override stored in lounge_assets.info_json["busyness"].
         Set via POST /lounges/{brand_id}/refresh-busyness by manager or admin.
         Expires after 4 hours to avoid stale data (falls through to next source).
      2. dgis — live congestion from 2GIS Catalog API. Used when info_json has
         dgis_branch_id or address. Cached for 30 min in info_json["busyness_2gis_cache"]
         to avoid hammering the API quota.
      3. checkins_last_hour — counts qr_checkin events in the last 60 min.
         If count > 0, normalize to 0-100 (15 checkins/h = 100%).
      4. mock_hourly — fallback when no real data is available.
         Uses hour-of-day curve + brand_id seed for variance.
    """
    import json as _json
    from app.services.dgis_busyness import (
        fetch_congestion_by_branch_id,
        fetch_congestion_by_address,
    )

    busyness_updated_at = None
    assets = db.query(LoungeAssets).filter(LoungeAssets.brand_id == brand_id).first()
    info: dict = {}
    if assets:
        try:
            parsed = _json.loads(assets.info_json or "{}")
            if isinstance(parsed, dict):
                info = parsed
        except Exception:
            info = {}

    def _level_for(p: int) -> str:
        if p < 25:
            return "quiet"
        if p < 55:
            return "moderate"
        if p < 80:
            return "busy"
        return "peak"

    # --- Path 0: Yandex Maps manual override (stored in info_json) ---
    bdata = info.get("busyness") if isinstance(info, dict) else None
    if isinstance(bdata, dict) and "percent" in bdata and "updated_at" in bdata:
        try:
            stored_at = datetime.fromisoformat(bdata["updated_at"])
            age_hours = (datetime.utcnow() - stored_at).total_seconds() / 3600
            if age_hours < 4:
                percent = int(bdata["percent"])
                return LoungeBusynessOut(
                    brand_id=brand_id,
                    percent=percent,
                    level=_level_for(percent),
                    source="yandex_maps",
                    updated_at=stored_at,
                )
        except Exception:
            pass  # malformed — fall through

    # --- Path 0.5: 2GIS live congestion (cached 30 min) ---
    dgis_branch_id = info.get("dgis_branch_id") if isinstance(info, dict) else None
    dgis_address = info.get("address") if isinstance(info, dict) else None
    cache = info.get("busyness_2gis_cache") if isinstance(info, dict) else None
    dgis_percent: Optional[int] = None
    dgis_cached_at: Optional[datetime] = None

    if isinstance(cache, dict) and "percent" in cache and "updated_at" in cache:
        try:
            cached_at = datetime.fromisoformat(cache["updated_at"])
            if (datetime.utcnow() - cached_at).total_seconds() < 1800:  # 30 min
                dgis_percent = int(cache["percent"])
                dgis_cached_at = cached_at
        except Exception:
            pass

    if dgis_percent is None and assets and (dgis_branch_id or dgis_address):
        fetched = None
        if dgis_branch_id:
            fetched = fetch_congestion_by_branch_id(str(dgis_branch_id))
        if fetched is None and dgis_address:
            fetched = fetch_congestion_by_address(str(dgis_address))
        if fetched is not None:
            dgis_percent = fetched
            dgis_cached_at = datetime.utcnow()
            info["busyness_2gis_cache"] = {
                "percent": fetched,
                "updated_at": dgis_cached_at.isoformat(),
            }
            try:
                assets.info_json = _json.dumps(info, ensure_ascii=False)
                assets.updated_at = dgis_cached_at
                db.commit()
            except Exception:
                db.rollback()

    if dgis_percent is not None:
        return LoungeBusynessOut(
            brand_id=brand_id,
            percent=dgis_percent,
            level=_level_for(dgis_percent),
            source="dgis",
            updated_at=dgis_cached_at,
        )

    # --- Path 1: real check-ins from the last hour ---
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    checkin_count = (
        db.query(func.count(LoungeBusinessEvent.id))
        .filter(
            LoungeBusinessEvent.brand_id == brand_id,
            LoungeBusinessEvent.event_type == "qr_checkin",
            LoungeBusinessEvent.created_at >= one_hour_ago,
        )
        .scalar()
    ) or 0

    MAX_CHECKINS_PER_HOUR = 15

    if checkin_count > 0:
        percent = min(int(checkin_count / MAX_CHECKINS_PER_HOUR * 100), 100)
        source = "checkins_last_hour"
    else:
        # --- Fallback: mock hourly curve + brand_id variance ---
        hour = datetime.utcnow().hour  # UTC hour (Moscow ≈ UTC+3)
        # Base load by hour of day
        if 0 <= hour < 7:
            base = 20
        elif 7 <= hour < 11:
            base = 10
        elif 11 <= hour < 16:
            base = 40
        elif 16 <= hour < 20:
            base = 70
        elif 20 <= hour < 23:
            base = 85
        else:
            base = 60
        # Deterministic variance from brand_id so each lounge looks different
        seed_offset = sum(ord(c) for c in brand_id) % 21 - 10  # -10 … +10
        percent = max(0, min(100, base + seed_offset))
        source = "mock_hourly"

    return LoungeBusynessOut(
        brand_id=brand_id,
        percent=percent,
        level=_level_for(percent),
        source=source,
        updated_at=busyness_updated_at,
    )


@app.post("/lounges/{brand_id}/refresh-busyness", response_model=LoungeBusynessOut)
def refresh_lounge_busyness(
    brand_id: str,
    payload: LoungeRefreshBusynessIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Manager/admin endpoint — manually set the current busyness % for a lounge.

    Stores the value in lounge_assets.info_json["busyness"] with a timestamp.
    GET /lounges/{brand_id}/busyness will return this as source="yandex_maps"
    for up to 4 hours before expiry.

    Optionally store yandex_org_id for future daemon integration:
      yandex_org_id — numeric org ID from yandex.ru/maps, e.g. "1024693268"
                       Found in URL: yandex.ru/maps/org/name/<ORG_ID>/

    Auth: must be lounge manager or admin.
    """
    import json as _json

    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    # Validate percent range
    if not (0 <= payload.percent <= 100):
        raise HTTPException(422, "percent must be between 0 and 100")

    # Load or create assets row
    assets = db.query(LoungeAssets).filter(LoungeAssets.brand_id == brand_id).first()
    if assets is None:
        assets = LoungeAssets(brand_id=brand_id, photo_urls="[]", info_json="{}")
        db.add(assets)
        db.flush()

    try:
        info = _json.loads(assets.info_json or "{}")
        if not isinstance(info, dict):
            info = {}
    except Exception:
        info = {}

    now = datetime.utcnow()

    # Update busyness sub-object
    info["busyness"] = {
        "percent": payload.percent,
        "updated_at": now.isoformat(),
        "set_by": current_user.username or current_user.email,
    }

    # Optionally store yandex_org_id for future daemon use
    if payload.yandex_org_id is not None:
        yid = payload.yandex_org_id.strip()
        if yid:
            info["yandex_org_id"] = yid

    # Optionally store 2GIS branch ID — enables auto busyness via 2GIS Catalog API
    if payload.dgis_branch_id is not None:
        did = payload.dgis_branch_id.strip()
        if did:
            info["dgis_branch_id"] = did

    # Manual override invalidates any cached 2GIS reading
    info.pop("busyness_2gis_cache", None)

    assets.info_json = _json.dumps(info, ensure_ascii=False)
    assets.updated_at = now
    db.commit()

    percent = payload.percent
    if percent < 25:
        level = "quiet"
    elif percent < 55:
        level = "moderate"
    elif percent < 80:
        level = "busy"
    else:
        level = "peak"

    return LoungeBusynessOut(
        brand_id=brand_id,
        percent=percent,
        level=level,
        source="yandex_maps",
        updated_at=now,
    )


# MARK: Lounge Broadcast Push — POST /lounges/{brand_id}/push (2026-05-28)
# Premium feature: Network or Partner tier only. Sends APNs push to all
# lounge subscribers. Returns {"sent": N}.
@app.post("/lounges/{brand_id}/push", tags=["lounges"])
def lounge_broadcast_push(
    brand_id: str,
    payload: LoungePushIn,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user),
):
    """Send a broadcast push notification to all subscribers of a lounge.

    Requires:
    - Bearer auth (lounge owner / manager)
    - Lounge billing tier >= network (network or partner)
    """
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id, db):
        raise HTTPException(403, "Business access required")

    # Tier gate — require_tier raises HTTP 402 when tier is too low.
    # We normalise that to a 403 with a machine-readable detail so iOS
    # can show an upsell screen instead of a generic error.
    try:
        require_tier(db, brand_id, "network")
    except HTTPException as _exc:
        if _exc.status_code == 402:
            raise HTTPException(403, detail="tier_required:network")
        raise

    subs = (
        db.query(LoungeSubscription)
        .filter(LoungeSubscription.brand_id == brand_id)
        .limit(5000)
        .all()
    )
    uid_list = [s.user_id for s in subs if s.user_id != current_user.id]

    if uid_list:
        try:
            import asyncio as _asyncio
            from app.push import send_push_fanout_async
            _asyncio.run(
                send_push_fanout_async(
                    db,
                    uid_list,
                    payload.title,
                    payload.body,
                    payload={"type": "lounge_announcement", "lounge_id": brand_id},
                )
            )
        except Exception as _e:
            print(f"[push] lounge-broadcast failed for {brand_id}: {_e}")

    return {"sent": len(uid_list)}


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

    return vote_mix_to_out(mix, 0.0, get_mix_cover_url(mix, db))


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

    # tags is a List[str] in the schema but TEXT(JSON) in the DB — encode here.
    import json as _json
    payload_dict = payload.dict(exclude={"ingredients", "tags"})
    payload_dict["tags"] = _json.dumps(payload.tags or [], ensure_ascii=False)
    # Default status to 'public' if caller omitted it.
    payload_dict["status"] = payload.status or "public"

    mix = Mix(
        author_id=user.id,
        **payload_dict
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

    # Drafts are private and don't count toward progression — no points until
    # the user explicitly publishes (PUT /mixes/{id} flipping status to public).
    if mix.status != "draft":
        award_event(
            user,
            "mix_created",
            db,
            description=f"Опубликован микс «{mix.name}»"
        )
    db.commit()
    db.refresh(mix)

    # APNs: notify lounge subscribers (topic_new_mix) when the mix is linked
    # to a lounge and published. Draft mixes skip the push.
    if mix.lounge_id and mix.status != "draft":
        try:
            import asyncio as _asyncio
            from app.push import send_push_fanout_async
            subs = db.query(LoungeSubscription).filter(
                LoungeSubscription.brand_id == mix.lounge_id,
                LoungeSubscription.topic_new_mix == True,  # noqa: E712
            ).limit(5000).all()
            push_title = "Новый микс"
            push_body = f"{mix.name}"
            push_payload = {
                "type": "mix",
                "mix_id": mix.id,
                "author_id": user.id,
                "lounge_id": mix.lounge_id,
            }
            uid_list = [s.user_id for s in subs if s.user_id != user.id]
            if uid_list:
                _asyncio.run(send_push_fanout_async(db, uid_list, push_title, push_body, payload=push_payload))
        except Exception as _e:
            print(f"[push] mix-create notify failed: {_e}")

    return mix_to_out(mix, user, db)


# MARK: Mix Wizard — POST /mixes/generate (rule-based AI, S2026-04-29)
@app.post("/mixes/generate", response_model=MixGenerateOut)
def generate_mix_from_brief(
    payload: MixGenerateIn,
    user: User = Depends(get_current_user),
):
    """
    Returns a generated mix recipe (name, description, 2-4 ingredients, tags).
    The recipe is NOT persisted — the iOS client decides whether to call
    POST /mixes with the same shape to save it.

    Phase 1 implementation is rule-based (see app/services/mix_wizard.py).
    A future phase will swap _pick_ingredients for an LLM call; the public
    contract stays stable.
    """
    if not user:
        raise HTTPException(401, "Unauthorized")

    if not (1 <= payload.strength <= 10):
        raise HTTPException(400, "strength must be in [1, 10]")

    from app.services.mix_wizard import generate_mix
    try:
        result = generate_mix(
            mood=payload.mood,
            strength=payload.strength,
            brands=payload.brands,
            occasion=payload.occasion,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return MixGenerateOut(**result)


# MARK: Mix Wizard — GET /users/me/mixes with status filter (S2026-04-29)
# MARK: Referrals — counter for ReferralView.
# Юзер: «не отображается сколько друзей позвал». Считаем по
# user_activities.event_type='referral_reward' — туда пишем при signup
# с referrer_code (см. ~line 2347). Каждая строка = 1 успешный реферал
# + 200 угольков начислено.
@app.get("/users/me/referrals")
def get_my_referrals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    current = get_required_user(user)
    rows = (
        db.query(UserActivity)
        .filter(
            UserActivity.user_id == current.id,
            UserActivity.event_type == "referral_reward"
        )
        .order_by(UserActivity.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "invited_count": len(rows),
        "total_bonus_earned": sum((r.points_delta or 0) for r in rows),
        "recent_invites": [
            {
                "title": r.title,
                "description": r.description,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "points": r.points_delta or 0,
            }
            for r in rows[:10]
        ],
    }


@app.get("/users/me/mixes", response_model=List[MixOut])
def list_my_mixes(
    status: Optional[str] = Query(None, description="Filter by status: 'public' | 'subscribers' | 'draft'"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Returns mixes authored by the caller. Default: all statuses (so iOS can
    show drafts alongside published in the profile). Pass ?status=draft to
    fetch only drafts (used by the Mix Wizard "saved drafts" tab).
    """
    if not user:
        raise HTTPException(401, "Unauthorized")

    query = db.query(Mix).options(
        joinedload(Mix.ingredients),
        joinedload(Mix.author),
    ).filter(Mix.author_id == user.id)

    if status:
        if status not in ("public", "subscribers", "draft"):
            raise HTTPException(400, f"unknown status: {status}")
        query = query.filter(Mix.status == status)

    mixes = query.order_by(Mix.created_at.desc(), Mix.id.desc()).all()
    return [mix_to_out(m, user, db) for m in mixes]


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

    import json as _json
    update_fields = payload.dict(exclude={"ingredients", "tags"})
    # tags arrives as List[str] in the payload, stored as JSON-encoded TEXT in DB.
    if payload.tags is not None:
        update_fields["tags"] = _json.dumps(payload.tags, ensure_ascii=False)
    # MixCreate.status defaults to 'public' on the wire (Pydantic default), so
    # the iOS client must round-trip the existing status when editing a draft.
    # That's intentional — the alternative (treating "missing" as "no change")
    # makes accidental publishes harder to spot.

    for field, value in update_fields.items():
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


@app.get("/users/me/lounge-bonuses", response_model=LoungeMyBonusesOut, tags=["loyalty"])
def my_lounge_bonuses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Список заведений, где у текущего юзера есть ненулевой бонусный баланс.
    Угольки — отдельно (GET /me). Это per-lounge бонусы, полученные на чек-инах.
    """
    current_user = get_required_user(user)
    rows = (
        db.query(LoungeGuestLoyalty)
        .filter(
            LoungeGuestLoyalty.user_id == current_user.id,
            LoungeGuestLoyalty.bonus_balance > 0,
        )
        .order_by(LoungeGuestLoyalty.bonus_balance.desc())
        .all()
    )
    items = [
        LoungeMyBonusItemOut(
            brand_id=r.brand_id,
            brand_title=display_title_from_brand_id(r.brand_id),
            bonus_balance=r.bonus_balance,
            rub_equivalent=r.bonus_balance // 10,
            visit_count=r.visit_count,
            last_visit_at=r.last_visit_at,
        )
        for r in rows
    ]
    return LoungeMyBonusesOut(
        items=items,
        total_balance=sum(r.bonus_balance for r in rows),
        total_rub=sum(r.bonus_balance // 10 for r in rows),
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
# LOUNGE SUBSCRIPTIONS — per-topic push settings
# ===============================================================

@app.put(
    "/lounges/{brand_id}/subscription",
    response_model=LoungeSubscriptionDTO,
    summary="Upsert per-topic push subscription for a lounge",
)
def upsert_lounge_subscription(
    brand_id: str,
    payload: LoungeSubscriptionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Subscribe or update topic toggles for a lounge.
    Omitted boolean fields keep the row's current value (or the default on first
    call). The row is identified by (user_id, brand_id).
    """
    current_user = get_required_user(user)
    sub = db.query(LoungeSubscription).filter(
        LoungeSubscription.user_id == current_user.id,
        LoungeSubscription.brand_id == brand_id,
    ).first()

    if sub is None:
        sub = LoungeSubscription(
            user_id=current_user.id,
            brand_id=brand_id,
            topic_events=payload.topic_events if payload.topic_events is not None else True,
            topic_new_mix=payload.topic_new_mix if payload.topic_new_mix is not None else True,
            topic_discounts=payload.topic_discounts if payload.topic_discounts is not None else True,
            topic_news=payload.topic_news if payload.topic_news is not None else False,
        )
        db.add(sub)
    else:
        if payload.topic_events is not None:
            sub.topic_events = payload.topic_events
        if payload.topic_new_mix is not None:
            sub.topic_new_mix = payload.topic_new_mix
        if payload.topic_discounts is not None:
            sub.topic_discounts = payload.topic_discounts
        if payload.topic_news is not None:
            sub.topic_news = payload.topic_news

    db.commit()
    db.refresh(sub)
    return LoungeSubscriptionDTO(
        brand_id=sub.brand_id,
        topic_events=sub.topic_events,
        topic_new_mix=sub.topic_new_mix,
        topic_discounts=sub.topic_discounts,
        topic_news=sub.topic_news,
    )


@app.delete(
    "/lounges/{brand_id}/subscription",
    response_model=StatusOut,
    summary="Unsubscribe from all push notifications for a lounge",
)
def delete_lounge_subscription(
    brand_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the subscription row entirely. Equivalent to turning all topics off."""
    current_user = get_required_user(user)
    sub = db.query(LoungeSubscription).filter(
        LoungeSubscription.user_id == current_user.id,
        LoungeSubscription.brand_id == brand_id,
    ).first()
    if sub:
        db.delete(sub)
        db.commit()
    return StatusOut(status="ok", message="unsubscribed")


@app.get(
    "/users/me/subscriptions",
    response_model=List[LoungeSubscriptionDTO],
    summary="List all lounge push subscriptions for the current user",
)
def list_my_subscriptions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns every lounge the user has explicitly subscribed to (via PUT endpoint)."""
    current_user = get_required_user(user)
    subs = db.query(LoungeSubscription).filter(
        LoungeSubscription.user_id == current_user.id,
    ).order_by(LoungeSubscription.brand_id).all()
    return [
        LoungeSubscriptionDTO(
            brand_id=s.brand_id,
            topic_events=s.topic_events,
            topic_new_mix=s.topic_new_mix,
            topic_discounts=s.topic_discounts,
            topic_news=s.topic_news,
        )
        for s in subs
    ]


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
            password_hash=hash_password(f"apple-{apple_sub}-no-password"),
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


# ── Telegram bot link (manager busyness polling) ────────────────────────────
@app.post("/me/telegram/link-code", response_model=TelegramLinkCodeOut)
def generate_telegram_link_code(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a one-time 6-digit code for linking the manager's Telegram account
    to their Hooka3 user. Manager sends `/start <code>` to the bot to bind.
    Code expires in 10 minutes.
    """
    import secrets as _secrets
    from app.core.config import TELEGRAM_BOT_USERNAME

    current_user = get_required_user(user)

    # Verify the user manages at least one brand (bot is useless otherwise)
    managed_brands = [
        bid for bid, usernames in BRAND_MANAGER_USERNAMES.items()
        if normalize_key(current_user.username) in usernames
        or normalize_key(current_user.email) in usernames
    ]
    if not managed_brands and not current_user.is_admin:
        raise HTTPException(403, "Only brand managers can link Telegram")

    code = f"{_secrets.randbelow(1_000_000):06d}"
    expires = datetime.utcnow() + timedelta(minutes=10)

    link = db.query(ManagerTelegramLink).filter(
        ManagerTelegramLink.user_id == current_user.id
    ).first()
    if link is None:
        link = ManagerTelegramLink(user_id=current_user.id)
        db.add(link)
    link.link_code = code
    link.code_expires_at = expires
    db.commit()

    return TelegramLinkCodeOut(
        code=code,
        expires_at=expires,
        bot_username=TELEGRAM_BOT_USERNAME,
        deep_link=f"https://t.me/{TELEGRAM_BOT_USERNAME}?start={code}",
    )


@app.get("/me/telegram/status", response_model=TelegramLinkStatusOut)
def get_telegram_link_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Whether the current manager has a verified Telegram link."""
    current_user = get_required_user(user)
    link = db.query(ManagerTelegramLink).filter(
        ManagerTelegramLink.user_id == current_user.id
    ).first()
    if link is None or link.verified_at is None:
        return TelegramLinkStatusOut(linked=False)
    return TelegramLinkStatusOut(
        linked=True,
        telegram_username=link.telegram_username,
        verified_at=link.verified_at,
    )


@app.delete("/me/telegram/link")
def unlink_telegram(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = get_required_user(user)
    link = db.query(ManagerTelegramLink).filter(
        ManagerTelegramLink.user_id == current_user.id
    ).first()
    if link is not None:
        db.delete(link)
        db.commit()
    return StatusOut(status="ok")


# ── Masters CRUD ─────────────────────────────────────────────────────────────

def _master_to_out(m: Master, current_user_id: Optional[int] = None, db: Optional[Session] = None) -> dict:
    """Convert Master ORM row to MasterOut-compatible dict.
    Adapts production column names (from_date/to_date) to iOS DTO names."""
    wh = []
    for w in (m.work_history or []):
        wh.append({
            "id": w.id,
            "lounge_id": w.lounge_id,
            "started_at": datetime.combine(w.from_date, datetime.min.time()) if w.from_date else None,
            "ended_at": datetime.combine(w.to_date, datetime.min.time()) if w.to_date else None,
            "is_current": w.to_date is None,
        })
    # is_following считаем только если есть current_user + db. Иначе false.
    is_following = False
    if current_user_id is not None and db is not None:
        is_following = db.query(MasterFollower).filter(
            MasterFollower.master_id == m.id,
            MasterFollower.user_id == current_user_id,
        ).first() is not None
    return {
        "id": m.id,
        "handle": m.handle,
        "display_name": m.display_name,
        "avatar_url": m.avatar_url,
        "bio": m.bio,
        "current_lounge_id": m.current_lounge_id,
        "rating": float(m.rating or 0.0),
        "followers_count": m.followers_count or 0,
        "mixes_count": m.mixes_count or 0,
        "reviews_count": m.reviews_count or 0,
        "is_verified": m.is_verified or False,
        "is_following": is_following,
        "work_history": wh,
    }


def _is_master_owner(master: Master, user: User) -> bool:
    username = normalize_key(user.username)
    return (
        (master.user_id is not None and master.user_id == user.id)
        or normalize_key(getattr(user, "master_profile_id", None)) == normalize_key(master.id)
        or (username != "" and username == normalize_key(master.handle))
    )


def _master_lounge_request_to_out(request: MasterLoungeRequest) -> MasterLoungeRequestOut:
    master = request.master
    if master is None:
        raise HTTPException(404, "Master not found")
    return MasterLoungeRequestOut(
        id=request.id,
        master_id=request.master_id,
        master_display_name=master.display_name,
        master_handle=master.handle,
        master_avatar_url=master.avatar_url,
        lounge_id=request.lounge_id,
        status=request.status,
        requested_by=request.requested_by,
        created_at=request.created_at,
        decided_at=request.decided_at,
    )


def _attach_master_to_lounge(master: Master, lounge_id: str, db: Session):
    from datetime import date as date_type

    today = date_type.today()
    open_entries = db.query(MasterWorkHistory).filter(
        MasterWorkHistory.master_id == master.id,
        MasterWorkHistory.to_date == None,  # noqa: E711
    ).all()
    has_current_same_lounge = any(entry.lounge_id == lounge_id for entry in open_entries)
    for entry in open_entries:
        if entry.lounge_id != lounge_id:
            entry.to_date = today
    if not has_current_same_lounge:
        db.add(MasterWorkHistory(
            master_id=master.id,
            lounge_id=lounge_id,
            from_date=today,
        ))
    master.current_lounge_id = lounge_id


def _recalc_master_rating(master_id: str, db: Session):
    """Recompute rating and reviews_count on masters from master_reviews."""
    rows = db.query(MasterReview).filter(
        MasterReview.master_id == master_id,
        MasterReview.is_hidden == False,
    ).all()
    count = len(rows)
    avg = round(sum(r.rating for r in rows) / count, 2) if count > 0 else 0.0
    master = db.query(Master).filter(Master.id == master_id).first()
    if master:
        master.rating = avg
        master.reviews_count = count


@app.get("/masters", response_model=MasterListOut)
def list_masters(
    lounge_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all masters with optional lounge_id filter. Paginated."""
    q = db.query(Master)
    if lounge_id:
        q = q.filter(Master.current_lounge_id == lounge_id)
    total = q.count()
    items = q.order_by(Master.followers_count.desc())\
             .offset((page - 1) * page_size)\
             .limit(page_size)\
             .all()
    return MasterListOut(
        items=[MasterOut(**_master_to_out(m, user.id if user else None, db)) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/masters/by-handle/{handle}", response_model=MasterOut)
def get_master_by_handle(
    handle: str,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch master profile by @handle."""
    master = db.query(Master).filter(Master.handle == handle).first()
    if not master:
        raise HTTPException(404, f"Master with handle '{handle}' not found")
    return MasterOut(**_master_to_out(master, user.id if user else None, db))


@app.get("/masters/{master_id}", response_model=MasterOut)
def get_master(
    master_id: str,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch master profile by id."""
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    return MasterOut(**_master_to_out(master, user.id if user else None, db))


@app.post("/masters", response_model=MasterOut)
def create_master(
    payload: MasterCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new master profile.

    Auth:
    - Admin может создать мастера для любого лаунжа
    - Lounge owner может создать мастера ТОЛЬКО для своего лаунжа
      (payload.current_lounge_id должен быть в его managed brands)
    """
    current_user = get_required_user(user)
    if not current_user.is_admin:
        # Не админ — должен быть менеджером целевого лаунжа.
        if not payload.current_lounge_id:
            raise HTTPException(
                403,
                "Lounge owners must specify current_lounge_id of their own venue",
            )
        if not can_manage_brand(current_user, payload.current_lounge_id):
            raise HTTPException(
                403,
                "You can only create masters for lounges you manage",
            )
    # Auto-gen id из handle если не передан клиентом.
    master_id = (payload.id or "").strip()
    if not master_id:
        slug = re.sub(r"[^a-z0-9_]+", "_", payload.handle.lower()).strip("_")
        master_id = f"master_{slug}" if slug else f"master_{uuid.uuid4().hex[:10]}"
        # На случай коллизии — добавим короткий суффикс.
        if db.query(Master).filter(Master.id == master_id).first():
            master_id = f"{master_id}_{uuid.uuid4().hex[:4]}"
    if db.query(Master).filter(Master.id == master_id).first():
        raise HTTPException(409, f"Master id '{master_id}' already exists")
    if db.query(Master).filter(Master.handle == payload.handle).first():
        raise HTTPException(409, f"Handle '{payload.handle}' already taken")
    master = Master(
        id=master_id,
        handle=payload.handle,
        display_name=payload.display_name,
        bio=payload.bio,
        avatar_url=payload.avatar_url,
        current_lounge_id=payload.current_lounge_id,
        mixes_count=payload.mixes_count,
        followers_count=payload.followers_count,
        rating=payload.rating,
    )
    db.add(master)
    db.commit()
    db.refresh(master)
    return MasterOut(**_master_to_out(master))


@app.patch("/masters/{master_id}", response_model=MasterOut)
def update_master(
    master_id: str,
    payload: MasterUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update master profile.

    Auth:
      • Сам мастер (`master.user_id == current_user.id`) — может править свой профиль
      • Админ — может всё
      • Владелец лаунжа — может ТОЛЬКО изменить `current_lounge_id` (прикрепить
        чужого мастера к своему заведению). Раньше получал 403, и юзер видел
        «Не удалось прикрепить» в iOS attachExistingMaster.
    """
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    is_own = (master.user_id is not None and master.user_id == current_user.id)
    is_admin = bool(current_user.is_admin)
    # Владелец заведения, к которому прикрепляют мастера, тоже допустим.
    # Проверяем что новый current_lounge_id принадлежит current_user.
    is_lounge_owner_attaching = (
        not is_own
        and not is_admin
        and payload.current_lounge_id is not None
        and can_manage_brand(current_user, payload.current_lounge_id)
    )
    if not is_own and not is_admin and not is_lounge_owner_attaching:
        raise HTTPException(403, "Not authorized to edit this master profile")
    # Lounge-owner ветка — позволяем менять ТОЛЬКО current_lounge_id,
    # остальные поля игнорируем (нельзя редактировать чужой bio/avatar).
    if is_own or is_admin:
        if payload.display_name is not None:
            master.display_name = payload.display_name
        if payload.bio is not None:
            master.bio = payload.bio
        if payload.avatar_url is not None:
            master.avatar_url = payload.avatar_url
    if payload.current_lounge_id is not None:
        master.current_lounge_id = payload.current_lounge_id
    db.commit()
    db.refresh(master)
    return MasterOut(**_master_to_out(master))


# ── Master lounge approval requests ───────────────────────────────────────────

@app.post("/masters/{master_id}/lounge-requests", response_model=MasterLoungeRequestOut)
def request_master_lounge_access(
    master_id: str,
    payload: MasterLoungeRequestIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    if not _is_master_owner(master, current_user) and not current_user.is_admin:
        raise HTTPException(403, "Not authorized")
    lounge_id = (payload.lounge_id or "").strip()
    if not lounge_id:
        raise HTTPException(400, "lounge_id is required")

    existing = db.query(MasterLoungeRequest).filter(
        MasterLoungeRequest.master_id == master_id,
        MasterLoungeRequest.lounge_id == lounge_id,
        MasterLoungeRequest.status == "pending",
    ).first()
    if existing:
        return _master_lounge_request_to_out(existing)

    request_row = MasterLoungeRequest(
        master_id=master_id,
        lounge_id=lounge_id,
        status="pending",
        requested_by=current_user.id,
    )
    db.add(request_row)
    db.commit()
    db.refresh(request_row)
    return _master_lounge_request_to_out(request_row)


@app.get("/lounges/{lounge_id}/master-requests", response_model=List[MasterLoungeRequestOut])
def get_lounge_master_requests(
    lounge_id: str,
    status: str = Query("pending"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, lounge_id):
        raise HTTPException(403, "Business access required")
    q = db.query(MasterLoungeRequest).filter(MasterLoungeRequest.lounge_id == lounge_id)
    if status:
        q = q.filter(MasterLoungeRequest.status == status)
    rows = q.order_by(MasterLoungeRequest.created_at.desc()).all()
    return [_master_lounge_request_to_out(row) for row in rows]


def _decide_lounge_master_request(
    lounge_id: str,
    request_id: int,
    status: str,
    user: User,
    db: Session,
) -> MasterLoungeRequestOut:
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, lounge_id):
        raise HTTPException(403, "Business access required")
    request_row = db.query(MasterLoungeRequest).filter(
        MasterLoungeRequest.id == request_id,
        MasterLoungeRequest.lounge_id == lounge_id,
    ).first()
    if not request_row:
        raise HTTPException(404, "Request not found")
    if request_row.status != "pending":
        return _master_lounge_request_to_out(request_row)

    request_row.status = status
    request_row.decided_by = current_user.id
    request_row.decided_at = datetime.utcnow()
    if status == "approved":
        master = db.query(Master).filter(Master.id == request_row.master_id).first()
        if not master:
            raise HTTPException(404, "Master not found")
        _attach_master_to_lounge(master, lounge_id, db)
        db.query(MasterLoungeRequest).filter(
            MasterLoungeRequest.master_id == request_row.master_id,
            MasterLoungeRequest.status == "pending",
            MasterLoungeRequest.id != request_row.id,
        ).update(
            {
                "status": "rejected",
                "decided_by": current_user.id,
                "decided_at": datetime.utcnow(),
            },
            synchronize_session=False,
        )
    db.commit()
    db.refresh(request_row)
    return _master_lounge_request_to_out(request_row)


@app.post("/lounges/{lounge_id}/master-requests/{request_id}/approve", response_model=MasterLoungeRequestOut)
def approve_lounge_master_request(
    lounge_id: str,
    request_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _decide_lounge_master_request(lounge_id, request_id, "approved", user, db)


@app.post("/lounges/{lounge_id}/master-requests/{request_id}/reject", response_model=MasterLoungeRequestOut)
def reject_lounge_master_request(
    lounge_id: str,
    request_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _decide_lounge_master_request(lounge_id, request_id, "rejected", user, db)


# ── Master work history ───────────────────────────────────────────────────────

@app.get("/masters/{master_id}/work-history", response_model=List[MasterWorkplaceOut])
def get_work_history(
    master_id: str,
    db: Session = Depends(get_db),
):
    """Return all work history entries for a master (oldest first)."""
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    rows = db.query(MasterWorkHistory)\
             .filter(MasterWorkHistory.master_id == master_id)\
             .order_by(MasterWorkHistory.from_date)\
             .all()
    result = []
    for w in rows:
        result.append(MasterWorkplaceOut(
            id=w.id,
            lounge_id=w.lounge_id,
            started_at=datetime.combine(w.from_date, datetime.min.time()) if w.from_date else None,
            ended_at=datetime.combine(w.to_date, datetime.min.time()) if w.to_date else None,
            is_current=(w.to_date is None),
        ))
    return result


@app.post("/masters/{master_id}/work-history", response_model=MasterWorkHistoryAddOut)
def add_work_history(
    master_id: str,
    payload: MasterWorkHistoryAddIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a new workplace for the master.
    Automatically closes current entry (sets to_date = today).
    Updates masters.current_lounge_id.
    Auth: master owner or admin.
    """
    from datetime import date as date_type
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    is_own = (master.user_id is not None and master.user_id == current_user.id)
    if not is_own and not current_user.is_admin:
        raise HTTPException(403, "Not authorized")
    try:
        started = date_type.fromisoformat(payload.started_at)
    except ValueError:
        raise HTTPException(400, "Invalid started_at date format, use YYYY-MM-DD")
    # Close currently open entries (to_date IS NULL)
    open_entries = db.query(MasterWorkHistory).filter(
        MasterWorkHistory.master_id == master_id,
        MasterWorkHistory.to_date == None,  # noqa: E711
    ).all()
    today = date_type.today()
    for entry in open_entries:
        entry.to_date = today
    # Create new entry
    new_entry = MasterWorkHistory(
        master_id=master_id,
        lounge_id=payload.lounge_id,
        from_date=started,
    )
    db.add(new_entry)
    master.current_lounge_id = payload.lounge_id
    db.commit()
    db.refresh(new_entry)
    return MasterWorkHistoryAddOut(
        status="ok",
        id=new_entry.id,
        master_id=master_id,
        lounge_id=payload.lounge_id,
    )


# MARK: - Master Shifts (расписание смен)
# Мастер указывает когда работает в каком зале — клиенты видят на профиле,
# подписчики получают пуш «твой мастер сегодня в lounge X с 19:00».

@app.get("/masters/{master_id}/shifts", response_model=MasterShiftsListOut)
def get_master_shifts(
    master_id: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """
    Список смен мастера. Без auth — публично, чтобы клиенты могли смотреть.
    Опциональные фильтры from_date/to_date — для календарной выборки на месяц.
    """
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    q = db.query(MasterShift).filter(MasterShift.master_id == master_id)
    if from_date is not None:
        q = q.filter(MasterShift.starts_at >= from_date)
    if to_date is not None:
        q = q.filter(MasterShift.starts_at <= to_date)
    rows = q.order_by(MasterShift.starts_at.asc()).all()
    return MasterShiftsListOut(
        items=[MasterShiftOut.model_validate(r) for r in rows],
        total=len(rows),
    )


@app.post("/masters/{master_id}/shifts", response_model=MasterShiftOut)
def create_master_shift(
    master_id: str,
    payload: MasterShiftCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Мастер добавляет смену. Auth: только сам мастер или админ.
    Валидация: ends_at > starts_at, длительность не более 16 часов
    (защита от опечаток вроде «начал 19:00, кончил 09:00 завтра» без даты).
    """
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    is_own = (master.user_id is not None and master.user_id == current_user.id)
    if not is_own and not current_user.is_admin:
        raise HTTPException(403, "Not authorized")
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(400, "ends_at must be after starts_at")
    duration_hours = (payload.ends_at - payload.starts_at).total_seconds() / 3600
    if duration_hours > 16:
        raise HTTPException(400, "Shift longer than 16 hours — split into multiple shifts")

    shift = MasterShift(
        master_id=master_id,
        lounge_id=payload.lounge_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        note=payload.note,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return MasterShiftOut.model_validate(shift)


@app.post("/masters/{master_id}/follow")
def follow_master(
    master_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Подписаться на мастера. Идемпотентно — повторный POST не создаёт дубль."""
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    existing = db.query(MasterFollower).filter(
        MasterFollower.master_id == master_id,
        MasterFollower.user_id == current_user.id,
    ).first()
    if existing is None:
        db.add(MasterFollower(master_id=master_id, user_id=current_user.id))
        # Инкремент счётчика подписчиков мастера.
        master.followers_count = (master.followers_count or 0) + 1
        db.commit()
    return {"status": "followed", "master_id": master_id, "is_following": True}


@app.delete("/masters/{master_id}/follow")
def unfollow_master(
    master_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Отписаться от мастера. Идемпотентно."""
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    existing = db.query(MasterFollower).filter(
        MasterFollower.master_id == master_id,
        MasterFollower.user_id == current_user.id,
    ).first()
    if existing is not None:
        db.delete(existing)
        master.followers_count = max(0, (master.followers_count or 0) - 1)
        db.commit()
    return {"status": "unfollowed", "master_id": master_id, "is_following": False}


@app.delete("/masters/{master_id}/shifts/{shift_id}")
def delete_master_shift(
    master_id: str,
    shift_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Мастер удаляет свою смену. Auth: только мастер-владелец или админ."""
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    is_own = (master.user_id is not None and master.user_id == current_user.id)
    if not is_own and not current_user.is_admin:
        raise HTTPException(403, "Not authorized")
    shift = db.query(MasterShift).filter(
        MasterShift.id == shift_id,
        MasterShift.master_id == master_id,
    ).first()
    if not shift:
        raise HTTPException(404, "Shift not found")
    db.delete(shift)
    db.commit()
    return {"status": "deleted", "id": shift_id}


@app.get("/shifts", response_model=MasterShiftsListOut)
def list_all_shifts(
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    lounge_id: Optional[str] = None,
    master_id: Optional[str] = None,
    followed_only: bool = False,
    limit: int = 100,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Глобальный список смен — клиент видит «кто сейчас работает». Подходит для:
    - Главной: «Сегодня на смене»
    - Lounge profile: смены в этом зале
    - Master profile: эквивалент /masters/{id}/shifts (если задан master_id)

    Каждая запись включает имя/handle/avatar мастера (single SQL via JOIN),
    чтобы клиент не делал N+1 запросов за деталями.
    """
    q = db.query(MasterShift, Master).join(
        Master, MasterShift.master_id == Master.id
    )
    if from_date is not None:
        q = q.filter(MasterShift.starts_at >= from_date)
    if to_date is not None:
        q = q.filter(MasterShift.starts_at <= to_date)
    if lounge_id is not None:
        q = q.filter(MasterShift.lounge_id == lounge_id)
    if followed_only and user is not None:
        followed_master_ids = db.query(MasterFollower.master_id).filter(
            MasterFollower.user_id == user.id
        ).subquery()
        q = q.filter(MasterShift.master_id.in_(followed_master_ids))
    if master_id is not None:
        q = q.filter(MasterShift.master_id == master_id)
    rows = q.order_by(MasterShift.starts_at.asc()).limit(min(limit, 500)).all()

    items = []
    for shift, master in rows:
        items.append(MasterShiftOut(
            id=shift.id,
            master_id=shift.master_id,
            lounge_id=shift.lounge_id,
            starts_at=shift.starts_at,
            ends_at=shift.ends_at,
            note=shift.note,
            created_at=shift.created_at,
            master_handle=master.handle,
            master_display_name=master.display_name,
            master_avatar_url=master.avatar_url,
        ))
    return MasterShiftsListOut(items=items, total=len(items))


@app.get("/masters/{master_id}/guest-stats", response_model=MasterGuestStatsOut)
def get_master_guest_stats(
    master_id: str,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Private stats for visits attributed to a master at QR check-in."""
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    is_owner = master.user_id == current_user.id if master.user_id is not None else False
    username_matches = normalize_key(current_user.username) == normalize_key(master.handle)
    if not current_user.is_admin and not is_owner and not username_matches:
        raise HTTPException(403, "Only this master can view guest stats")

    q = db.query(LoungeBusinessEvent).filter(
        LoungeBusinessEvent.event_type == "qr_checkin",
        LoungeBusinessEvent.master_id == master_id,
    )
    if from_date is not None:
        q = q.filter(LoungeBusinessEvent.created_at >= from_date)
    if to_date is not None:
        q = q.filter(LoungeBusinessEvent.created_at <= to_date)

    visits = q.order_by(LoungeBusinessEvent.created_at.desc()).all()
    guest_visit_counts = defaultdict(int)
    for visit in visits:
        if visit.guest_user_id is not None:
            guest_visit_counts[visit.guest_user_id] += 1

    bundle_q = db.query(LoungeBundleVisit).filter(
        LoungeBundleVisit.master_id == master_id,
    )
    if from_date is not None:
        bundle_q = bundle_q.filter(LoungeBundleVisit.visited_at >= from_date)
    if to_date is not None:
        bundle_q = bundle_q.filter(LoungeBundleVisit.visited_at <= to_date)
    bundle_visits = bundle_q.all()
    bundle_count = len(bundle_visits)
    compensation = sum(v.compensation_rub for v in bundle_visits)

    recent: list[MasterGuestVisitOut] = []
    for visit in visits[:12]:
        if visit.guest_user_id is None:
            continue
        guest = db.query(User).filter(User.id == visit.guest_user_id).first()
        window_start = visit.created_at - timedelta(minutes=5)
        window_end = visit.created_at + timedelta(minutes=5)
        bundle = db.query(LoungeBundleVisit).filter(
            LoungeBundleVisit.master_id == master_id,
            LoungeBundleVisit.user_id == visit.guest_user_id,
            LoungeBundleVisit.brand_id == visit.brand_id,
            LoungeBundleVisit.visited_at >= window_start,
            LoungeBundleVisit.visited_at <= window_end,
        ).first()
        recent.append(MasterGuestVisitOut(
            id=visit.id,
            brand_id=visit.brand_id,
            guest_user_id=visit.guest_user_id,
            guest_username=(guest.username if guest else None) or f"user_{visit.guest_user_id}",
            visited_at=visit.created_at,
            bundle_redeemed=bundle is not None,
            compensation_rub=bundle.compensation_rub if bundle else 0,
        ))

    return MasterGuestStatsOut(
        master_id=master_id,
        total_visits=len(visits),
        unique_guests=len(guest_visit_counts),
        repeat_guests=sum(1 for count in guest_visit_counts.values() if count > 1),
        bundle_redemptions=bundle_count,
        compensation_rub=compensation,
        recent_visits=recent,
    )


# ── Master reviews ────────────────────────────────────────────────────────────

@app.get("/masters/{master_id}/reviews", response_model=MasterReviewsListOut)
def list_master_reviews(
    master_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List reviews for a master, paginated, newest first. Excludes hidden."""
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    q = db.query(MasterReview).filter(
        MasterReview.master_id == master_id,
        MasterReview.is_hidden == False,
    )
    total = q.count()
    rows = q.order_by(MasterReview.created_at.desc())\
            .offset((page - 1) * page_size)\
            .limit(page_size)\
            .all()
    items = []
    for r in rows:
        author = db.query(User).filter(User.id == r.user_id).first()
        items.append(MasterReviewOut(
            id=r.id,
            master_id=r.master_id,
            author_user_id=r.user_id,
            author_display_name=author.username if author else None,
            author_avatar_url=None,
            rating=r.rating,
            text=r.body or "",
            created_at=r.created_at,
            master_response_text=r.master_response_text,
            master_responded_at=r.master_responded_at,
            is_hidden=r.is_hidden,
        ))
    return MasterReviewsListOut(items=items, total=total, page=page, page_size=page_size)


@app.post("/masters/{master_id}/reviews", response_model=MasterReviewOut)
def create_master_review(
    master_id: str,
    payload: MasterReviewCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a review for a master.
    Auth: any logged-in user, NOT the master themselves.
    Triggers rating recalculation.
    """
    current_user = get_required_user(user)
    master = db.query(Master).filter(Master.id == master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    if master.user_id is not None and master.user_id == current_user.id:
        raise HTTPException(400, "Cannot review your own master profile")
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(400, "Rating must be between 1 and 5")
    if not payload.text or not payload.text.strip():
        raise HTTPException(400, "Review text cannot be empty")
    review = MasterReview(
        master_id=master_id,
        user_id=current_user.id,       # production column name is user_id
        rating=payload.rating,
        body=payload.text.strip(),     # production column name is body
    )
    db.add(review)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You have already reviewed this master")
    _recalc_master_rating(master_id, db)
    db.commit()
    db.refresh(review)
    author = db.query(User).filter(User.id == current_user.id).first()
    return MasterReviewOut(
        id=review.id,
        master_id=review.master_id,
        author_user_id=review.user_id,
        author_display_name=author.username if author else None,
        author_avatar_url=None,
        rating=review.rating,
        text=review.body or "",
        created_at=review.created_at,
        master_response_text=None,
        master_responded_at=None,
        is_hidden=review.is_hidden,
    )


# ── Master review responses ───────────────────────────────────────────────────

@app.post("/reviews/{review_id}/master-response", response_model=MasterResponseOut)
def add_master_response(
    review_id: int,
    payload: MasterResponseCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Master responds to a review. Auth: only the master to whom the review belongs."""
    current_user = get_required_user(user)
    review = db.query(MasterReview).filter(MasterReview.id == review_id).first()
    if not review:
        raise HTTPException(404, "Review not found")
    master = db.query(Master).filter(Master.id == review.master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    is_master_owner = (master.user_id is not None and master.user_id == current_user.id)
    if not is_master_owner and not current_user.is_admin:
        raise HTTPException(403, "Only the master can respond to their own review")
    if review.master_response_text is not None:
        raise HTTPException(409, "Response already exists. Use PATCH to update.")
    if not payload.text or not payload.text.strip():
        raise HTTPException(400, "Response text cannot be empty")
    review.master_response_text = payload.text.strip()
    review.master_responded_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return MasterResponseOut(
        review_id=review.id,
        master_response_text=review.master_response_text,
        master_responded_at=review.master_responded_at,
    )


@app.patch("/reviews/{review_id}/master-response", response_model=MasterResponseOut)
def update_master_response(
    review_id: int,
    payload: MasterResponseCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edit master's response. Auth: master owner or admin."""
    current_user = get_required_user(user)
    review = db.query(MasterReview).filter(MasterReview.id == review_id).first()
    if not review:
        raise HTTPException(404, "Review not found")
    master = db.query(Master).filter(Master.id == review.master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    is_master_owner = (master.user_id is not None and master.user_id == current_user.id)
    if not is_master_owner and not current_user.is_admin:
        raise HTTPException(403, "Only the master can edit their response")
    if review.master_response_text is None:
        raise HTTPException(404, "No response exists. Use POST first.")
    if not payload.text or not payload.text.strip():
        raise HTTPException(400, "Response text cannot be empty")
    review.master_response_text = payload.text.strip()
    review.master_responded_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return MasterResponseOut(
        review_id=review.id,
        master_response_text=review.master_response_text,
        master_responded_at=review.master_responded_at,
    )


@app.delete("/reviews/{review_id}/master-response", response_model=StatusOut)
def delete_master_response(
    review_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete master's response. Auth: master owner or admin."""
    current_user = get_required_user(user)
    review = db.query(MasterReview).filter(MasterReview.id == review_id).first()
    if not review:
        raise HTTPException(404, "Review not found")
    master = db.query(Master).filter(Master.id == review.master_id).first()
    if not master:
        raise HTTPException(404, "Master not found")
    is_master_owner = (master.user_id is not None and master.user_id == current_user.id)
    if not is_master_owner and not current_user.is_admin:
        raise HTTPException(403, "Only the master can delete their response")
    if review.master_response_text is None:
        raise HTTPException(404, "No response to delete")
    review.master_response_text = None
    review.master_responded_at = None
    db.commit()
    return StatusOut(status="ok", message="Master response deleted")


# ── Account deletion (App Store 5.1.1(v)) ─────────────────────────────────
# Soft delete: set is_deleted=True and scrub PII so the row is unrecoverable
# for human readers but cascading FKs (mixes/comments) remain intact so other
# users' data isn't broken. get_current_user rejects deleted accounts.

@app.delete("/users/me", response_model=AccountDeleteOut)
def delete_my_account(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """User-initiated account deletion. App Store 5.1.1(v) compliance."""
    current = get_required_user(user)
    deleted_id = current.id
    current.email = f"deleted-{deleted_id}@deleted.local"
    current.username = f"deleted_{deleted_id}"
    current.password_hash = ""
    current.display_name = None
    current.phone = None
    current.bio = None
    current.city = None
    current.avatar_url = None
    current.ton_address = None
    current.is_deleted = True
    db.commit()
    return AccountDeleteOut(status="deleted", user_id=deleted_id)


# ── Master avatar upload (POST /me/master/avatar) ─────────────────────────
# iOS sends JSON {file_name, mime_type, data_base64}; we save under
# /app/static/uploads/avatars/{user_id}/{ts}.jpg and return the public URL.
# If the user has a master profile, master.avatar_url is also updated.

import base64 as _base64

_AVATAR_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_AVATAR_MAX_DIM = 1024


def _save_avatar_bytes(user_id: int, raw: bytes, mime_type: str) -> str:
    """Persist raw image bytes to /app/static/uploads/avatars/{user_id}/{ts}.jpg.
    Resizes to max 1024×1024 if Pillow is available; otherwise saves raw.
    Returns public URL like /static/uploads/avatars/61/1714867200000.jpg."""
    if len(raw) > _AVATAR_MAX_BYTES:
        raise HTTPException(413, "Image too large (max 5 MB)")
    if not (mime_type or "").lower().startswith("image/"):
        raise HTTPException(400, "Unsupported file type — image/* required")
    ext = "jpg"
    lowered = (mime_type or "").lower()
    if "png" in lowered:
        ext = "png"
    elif "webp" in lowered:
        ext = "webp"
    elif "heic" in lowered or "heif" in lowered:
        ext = "heic"
    ts = int(datetime.utcnow().timestamp() * 1000)
    fname = f"{ts}.{ext}"
    upload_bytes = raw
    content_type = mime_type or "image/jpeg"
    # Best-effort resize (degrades gracefully if Pillow not installed).
    try:
        from PIL import Image  # type: ignore
        from io import BytesIO
        img = Image.open(BytesIO(raw))
        img.thumbnail((_AVATAR_MAX_DIM, _AVATAR_MAX_DIM))
        buf = BytesIO()
        save_format = "JPEG" if ext in ("jpg", "jpeg", "heic") else (
            "PNG" if ext == "png" else "WEBP"
        )
        if save_format == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format=save_format, quality=85)
        upload_bytes = buf.getvalue()
        # If we re-encoded heic to jpeg, fix extension/content-type.
        if ext == "heic":
            ext = "jpg"
            fname = f"{ts}.{ext}"
            content_type = "image/jpeg"
    except Exception as e:
        # Pillow missing or decode failed — upload the raw bytes as-is.
        print(f"[avatar] pillow fallback: {e}")

    # Upload via storage abstraction (local or S3 depending on ENV).
    from app.services.storage import get_storage as _get_storage
    key = f"uploads/avatars/{user_id}/{fname}"
    url = _get_storage().upload(key, upload_bytes, content_type)
    return url


@app.post("/me/master/avatar")
def upload_master_avatar(
    payload: MasterAvatarUploadIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload an avatar image for the calling user. If they own a Master
    profile, also updates master.avatar_url. iOS sends base64 JSON, see
    `MixAPI.uploadMyMasterAvatar`."""
    current = get_required_user(user)
    if not payload.data_base64:
        raise HTTPException(400, "data_base64 is required")
    try:
        raw = _base64.b64decode(payload.data_base64, validate=False)
    except Exception:
        raise HTTPException(400, "Invalid base64 payload")
    url = _save_avatar_bytes(current.id, raw, payload.mime_type or "image/jpeg")
    # Persist to user record.
    current.avatar_url = url
    # Also update master if one exists for this user.
    master = db.query(Master).filter(Master.user_id == current.id).first()
    if master:
        master.avatar_url = url
    db.commit()
    if master:
        db.refresh(master)
        return MasterOut(**_master_to_out(master, current.id, db))
    return {"url": url, "avatar_url": url}


# ── User avatar upload (POST /me/avatar) ──────────────────────────────────
# Any logged-in user can set their own profile photo via multipart upload.
# Delegates bytes persistence to _save_avatar_bytes (same as master avatar).

@app.post("/me/avatar")
def upload_user_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a profile avatar for the currently authenticated user.
    Accepts multipart/form-data with field `file` (jpeg or png).
    Returns {avatar_url}."""
    current = get_required_user(user)
    raw = file.file.read()
    mime_type = file.content_type or "image/jpeg"
    url = _save_avatar_bytes(current.id, raw, mime_type)
    current.avatar_url = url
    db.commit()
    return {"avatar_url": url}


# ── Tobacco flavors catalog (GET /flavors) ────────────────────────────────
# Filters: brand (substring ILIKE), category (exact), search (ILIKE on name).
# Backed by tobacco_flavors (276 rows). Raw SQL — no ORM model needed for MVP.

@app.get("/flavors", response_model=TobaccoFlavorListOut)
def list_tobacco_flavors(
    brand: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated list of tobacco flavors. Public — no auth required."""
    where = ["TRUE"]
    params: dict = {"limit": limit, "offset": offset}
    if brand:
        where.append("brand ILIKE :brand")
        params["brand"] = f"%{brand}%"
    if category:
        where.append("category = :category")
        params["category"] = category
    if search:
        where.append("name ILIKE :search")
        params["search"] = f"%{search}%"
    clause = " AND ".join(where)
    total_row = db.execute(
        sa_text(f"SELECT COUNT(*) FROM tobacco_flavors WHERE {clause}"),
        params,
    ).first()
    total = int(total_row[0]) if total_row else 0
    rows = db.execute(
        sa_text(
            f"SELECT id, brand, name, category, strength, description, image_url, color "
            f"FROM tobacco_flavors WHERE {clause} "
            f"ORDER BY brand, name LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings().all()
    items = [TobaccoFlavorOut(**dict(r)) for r in rows]
    return TobaccoFlavorListOut(items=items, total=total, limit=limit, offset=offset)


# ── Single flavor by id (GET /flavors/{flavor_id}) ───────────────────────
# Юзер 2026-05-27: «вместо имени флейвора показывается Загрузка...» —
# раньше iOS должен был грузить весь /flavors?brand=... и искать match.
# Это медленно и часто фейлится из-за неточного match. Direct lookup —
# единственный надёжный путь.

@app.get("/flavors/{flavor_id}", response_model=TobaccoFlavorOut)
def get_tobacco_flavor(flavor_id: int, db: Session = Depends(get_db)):
    """Single flavor by id. Public — no auth required."""
    row = db.execute(
        sa_text(
            "SELECT id, brand, name, category, strength, description, "
            "image_url, source AS source_url FROM tobacco_flavors WHERE id = :id"
        ),
        {"id": flavor_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="flavor_not_found")
    return TobaccoFlavorOut(**dict(row))


# ── Tobacco brands catalog (GET /tobacco/brands) ─────────────────────────
# Returns distinct brands grouped from tobacco_flavors with flavor count.
# category filter: 'tobacco' | 'liquid'

@app.get("/tobacco/brands", response_model=TobaccoBrandListOut)
@limiter.limit("60/minute")
def list_tobacco_brands(
    request: Request,
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Distinct brands list with flavor counts. Public — no auth required."""
    where = ["TRUE"]
    params: dict = {}
    if category:
        where.append("category = :category")
        params["category"] = category
    clause = " AND ".join(where)
    rows = db.execute(
        sa_text(
            f"SELECT brand, COALESCE(category, 'tobacco') as category, COUNT(*) as flavor_count "
            f"FROM tobacco_flavors WHERE {clause} "
            f"GROUP BY brand, category ORDER BY brand"
        ),
        params,
    ).mappings().all()
    items = [TobaccoBrandOut(**dict(r)) for r in rows]
    return TobaccoBrandListOut(items=items, total=len(items))


@app.get("/tobacco/brands/{brand_name}/flavors", response_model=TobaccoBrandFlavorsOut)
@limiter.limit("60/minute")
def list_brand_flavors(
    request: Request,
    brand_name: str,
    db: Session = Depends(get_db),
):
    """All flavor names for a specific brand. Public — no auth required.
    brand_name is the brand label (e.g. 'Morpheus', 'TNG', 'TROFIMOFF\"S').
    """
    row = db.execute(
        sa_text(
            "SELECT brand, COALESCE(category, 'tobacco') as category, "
            "ARRAY_AGG(name ORDER BY name) as flavors, COUNT(*) as total "
            "FROM tobacco_flavors WHERE brand ILIKE :brand GROUP BY brand, category"
        ),
        {"brand": brand_name},
    ).first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Brand not found")
    return TobaccoBrandFlavorsOut(
        brand=row[0],
        category=row[1],
        flavors=list(row[2]),
        total=int(row[3]),
    )


# ── Tobacco mix templates (GET /mix-templates) ────────────────────────────
# Returns templates plus their full ingredient list. Filters by primary_brand
# (substring), mood (exact). Backed by tobacco_mix_templates (396 rows) and
# tobacco_mix_template_ingredients.

@app.get("/mix-templates", response_model=TobaccoMixTemplateListOut)
@limiter.limit("60/minute")
def list_tobacco_mix_templates(
    request: Request,
    brand: Optional[str] = Query(None),
    mood: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    source: Optional[str] = Query(None),  # community | scraped | etc.
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated list of tobacco mix templates with full ingredients.

    Use `source=community` to get only curated community presets seeded
    via seed_mix_templates_2026_05_25.py (12 entries) — these are what the
    wizard «Из шаблона» step shows. Without filter you get every template
    including scraped/imported ones (~400 rows).
    """
    where = ["TRUE"]
    params: dict = {"limit": limit, "offset": offset}
    if brand:
        where.append("primary_brand ILIKE :brand")
        params["brand"] = f"%{brand}%"
    if mood:
        where.append("mood = :mood")
        params["mood"] = mood
    if search:
        where.append("name ILIKE :search")
        params["search"] = f"%{search}%"
    if source:
        where.append("source = :source")
        params["source"] = source
    clause = " AND ".join(where)
    total_row = db.execute(
        sa_text(f"SELECT COUNT(*) FROM tobacco_mix_templates WHERE {clause}"),
        params,
    ).first()
    total = int(total_row[0]) if total_row else 0
    template_rows = db.execute(
        sa_text(
            f"SELECT id, name, description, primary_brand, mood, strength_score, image_url "
            f"FROM tobacco_mix_templates WHERE {clause} "
            f"ORDER BY id LIMIT :limit OFFSET :offset"
        ),
        params,
    ).mappings().all()
    template_ids = [r["id"] for r in template_rows]
    ingredients_by_template: dict[int, list[TobaccoMixTemplateIngredientOut]] = {
        tid: [] for tid in template_ids
    }
    if template_ids:
        ing_rows = db.execute(
            sa_text(
                "SELECT template_id, flavor_id, brand, flavor_name, percentage, position "
                "FROM tobacco_mix_template_ingredients "
                "WHERE template_id = ANY(:ids) "
                "ORDER BY template_id, position"
            ),
            {"ids": list(template_ids)},
        ).mappings().all()
        for r in ing_rows:
            ingredients_by_template.setdefault(r["template_id"], []).append(
                TobaccoMixTemplateIngredientOut(
                    brand=r.get("brand"),
                    flavor=r.get("flavor_name"),
                    flavor_id=r.get("flavor_id"),
                    percentage=r.get("percentage"),
                    position=r["position"],
                )
            )
    items = [
        TobaccoMixTemplateOut(
            id=r["id"],
            name=r["name"],
            description=r.get("description"),
            primary_brand=r["primary_brand"],
            mood=r.get("mood"),
            strength_score=r.get("strength_score"),
            image_url=r.get("image_url"),
            ingredients=ingredients_by_template.get(r["id"], []),
        )
        for r in template_rows
    ]
    return TobaccoMixTemplateListOut(items=items, total=total, limit=limit, offset=offset)


# ── Leaderboard / Medals (LOOMIX parity, S2026-05-15) ───────────────────────
from app.services import leaderboard as _leaderboard_svc


def _user_avatar_url(user: Optional[User]) -> Optional[str]:
    if not user:
        return None
    return user.avatar_url


def _ranked_row_to_entry(
    row: "_leaderboard_svc.RankedRow",
    rank: int,
    db: Session,
) -> LeaderboardEntryOut:
    medal = _leaderboard_svc.MEDALS_BY_RANK.get(rank)
    return LeaderboardEntryOut(
        rank=rank,
        medal=medal,
        mix_id=row.mix.id,
        mix_name=row.mix.name,
        mix_cover_url=get_mix_cover_url(row.mix, db),
        user_id=row.mix.author_id,
        username=row.mix.author.username if row.mix.author else None,
        avatar_url=_user_avatar_url(row.mix.author),
        likes_count=row.likes_count,
    )


@app.get("/leaderboard", response_model=LeaderboardOut)
def get_leaderboard(
    period: str = Query("week", regex="^(week|month)$"),
    limit: int = Query(10, ge=1, le=50),
    category: str = Query("mixes", regex="^(mixes)$"),
    db: Session = Depends(get_db),
):
    """Top mixes podium for the current week or month (MSK)."""
    start_dt, end_dt, _ = _leaderboard_svc.bounds_for(period)
    rows = _leaderboard_svc.top_mixes_in_window(db, start_dt, end_dt, limit=limit)
    entries = [_ranked_row_to_entry(row, idx + 1, db) for idx, row in enumerate(rows)]
    return LeaderboardOut(
        period=period,
        period_start=start_dt,
        period_end=end_dt,
        category=category,
        entries=entries,
    )


@app.get("/users/{user_id}/stats", response_model=UserPublicStatsOut)
def get_user_public_stats(user_id: int, db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    payload = _leaderboard_svc.user_public_stats(db, target)
    return UserPublicStatsOut(
        posts_count=payload["posts_count"],
        likes_received=payload["likes_received"],
        comments_made=payload["comments_made"],
        followers_count=payload["followers_count"],
        following_count=payload["following_count"],
        medals=MedalCountsOut(**payload["medals"]),
    )


@app.get("/users/{user_id}/medals", response_model=List[UserMedalOut])
def get_user_medals(user_id: int, db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    rows = (
        db.query(UserMedal)
        .filter(UserMedal.user_id == user_id)
        .order_by(UserMedal.period_start.desc(), UserMedal.created_at.desc())
        .all()
    )
    out: List[UserMedalOut] = []
    mix_cache: dict[int, Mix] = {}
    for medal in rows:
        mix = None
        if medal.mix_id is not None:
            mix = mix_cache.get(medal.mix_id)
            if mix is None:
                mix = db.query(Mix).filter(Mix.id == medal.mix_id).first()
                if mix is not None:
                    mix_cache[mix.id] = mix
        out.append(
            UserMedalOut(
                id=medal.id,
                medal_type=medal.medal_type,
                period_type=medal.period_type,
                period_start=datetime.combine(medal.period_start, datetime.min.time()),
                likes_count=int(medal.likes_count or 0),
                mix_id=medal.mix_id,
                mix_name=mix.name if mix else None,
                mix_cover_url=get_mix_cover_url(mix, db) if mix else None,
                created_at=medal.created_at,
            )
        )
    return out


@app.post("/admin/medals/backfill", response_model=MedalBackfillOut)
def admin_medals_backfill(
    period: str = Query("week", regex="^(week|month)$"),
    date: Optional[str] = Query(
        None,
        description="ISO date (YYYY-MM-DD) inside the period to backfill. "
                    "Defaults to today MSK (i.e. grants medals for the period "
                    "that just ended).",
    ),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    reference: Optional[datetime] = None
    if date:
        try:
            parsed = datetime.fromisoformat(date)
        except ValueError:
            raise HTTPException(400, "date must be YYYY-MM-DD")
        # Anchor inside the period that contains `date` — the grant
        # function will then award medals for the period BEFORE it.
        # So if the caller wants to grant medals for "week ending Sun May 11",
        # they pass date = anything in week May 12-18 (next week).
        reference = parsed.replace(tzinfo=_leaderboard_svc.MSK_TZ)
    summary = _leaderboard_svc.grant_medals_for_period(db, period, reference)
    # Rebuild leaderboard entries for response (so iOS/admin can show the
    # podium that was just awarded).
    start_dt, end_dt, _ = _leaderboard_svc.prev_bounds_for(period, reference)
    rows = _leaderboard_svc.top_mixes_in_window(db, start_dt, end_dt, limit=3)
    entries = [_ranked_row_to_entry(row, idx + 1, db) for idx, row in enumerate(rows)]
    return MedalBackfillOut(
        period_type=period,
        period_start=datetime.combine(summary["period_start"], datetime.min.time()),
        granted=summary["granted"],
        skipped_existing=summary["skipped"],
        entries=entries,
    )


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


# -------------------------------------------------------------------
# MARK: CRM endpoints — owner analytics (2026-05-26)
# -------------------------------------------------------------------

@app.get("/lounges/{brand_id}/crm/stats", response_model=LoungeCrmStatsOut, tags=["crm"])
@limiter.limit("60/minute")
def lounge_crm_stats(
    request: Request,
    brand_id: str,
    period: str = Query("month", regex="^(week|month|all)$"),
    # Юзер: «пиковые часы не правильно показываются по GMT устройства должно
    # смотреть». iOS передаёт TimeZone.current.secondsFromGMT()/60 — для
    # Москвы это +180. Сдвигаем UTC-created_at на это смещение перед
    # вычислением hour/weekday.
    tz_offset_min: int = Query(0, ge=-720, le=840),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aggregate CRM stats for a lounge. Owner-only. Requires tier >= pro."""
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")
    if not current_user.is_admin:
        require_tier(db, brand_id, "pro")

    now = datetime.utcnow()
    if period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = None

    base_q = db.query(LoungeVisit).filter(LoungeVisit.brand_id == brand_id)
    if since:
        base_q = base_q.filter(LoungeVisit.created_at >= since)

    visits = base_q.all()

    visits_count = len(visits)
    if visits_count == 0:
        return LoungeCrmStatsOut(
            period=period,
            visits_count=0,
            unique_guests=0,
            total_revenue=0,
            avg_bill=0,
            repeat_rate=0.0,
            new_guests=0,
            top_hours=[],
            top_weekdays=[],
        )

    total_revenue = sum(v.bill_amount for v in visits)
    avg_bill = total_revenue // visits_count if visits_count else 0

    # Unique guests in period
    guest_ids_in_period = {v.user_id for v in visits}
    unique_guests = len(guest_ids_in_period)

    # Repeat rate — % guests with >= 2 visits in period
    from collections import Counter as _Counter
    user_visit_counts = _Counter(v.user_id for v in visits)
    repeat_guests = sum(1 for c in user_visit_counts.values() if c >= 2)
    repeat_rate = round(repeat_guests / unique_guests * 100, 1) if unique_guests else 0.0

    # New guests — users whose FIRST visit ever at this brand falls in period
    if since:
        # For each guest in period, find their earliest visit ever
        new_guests = 0
        for uid in guest_ids_in_period:
            earliest = db.query(func.min(LoungeVisit.created_at)).filter(
                LoungeVisit.brand_id == brand_id,
                LoungeVisit.user_id == uid,
            ).scalar()
            if earliest and earliest >= since:
                new_guests += 1
    else:
        new_guests = unique_guests  # all = all are "new" in all-time context

    # Top hours (24 buckets, return top 5). Сдвигаем UTC → tz клиента.
    tz_delta = timedelta(minutes=tz_offset_min)
    hour_counts: dict = {}
    for v in visits:
        local_dt = v.created_at + tz_delta
        h = local_dt.hour
        hour_counts[h] = hour_counts.get(h, 0) + 1
    top_hours_raw = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_hours = [HourBucket(hour=h, count=c) for h, c in sorted(top_hours_raw, key=lambda x: x[1], reverse=True)]

    # Weekdays (0=Mon ISO — Python weekday() already gives 0=Mon). Тоже сдвигаем.
    weekday_counts: dict = {}
    for v in visits:
        local_dt = v.created_at + tz_delta
        wd = local_dt.weekday()
        weekday_counts[wd] = weekday_counts.get(wd, 0) + 1
    top_weekdays = [WeekdayBucket(weekday=wd, count=c) for wd, c in sorted(weekday_counts.items(), key=lambda x: x[0])]

    return LoungeCrmStatsOut(
        period=period,
        visits_count=visits_count,
        unique_guests=unique_guests,
        total_revenue=total_revenue,
        avg_bill=avg_bill,
        repeat_rate=repeat_rate,
        new_guests=new_guests,
        top_hours=top_hours,
        top_weekdays=top_weekdays,
    )


@app.get("/lounges/{brand_id}/crm/regulars", response_model=LoungeCrmRegularsOut, tags=["crm"])
@limiter.limit("60/minute")
def lounge_crm_regulars(
    request: Request,
    brand_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Top guests by visit count. Owner-only. Requires tier >= pro."""
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")
    if not current_user.is_admin:
        require_tier(db, brand_id, "pro")

    # Aggregate per user
    from sqlalchemy import func as _func

    agg = (
        db.query(
            LoungeVisit.user_id,
            _func.count(LoungeVisit.id).label("visits_count"),
            _func.sum(LoungeVisit.bill_amount).label("total_spent"),
            _func.max(LoungeVisit.created_at).label("last_visit_at"),
        )
        .filter(LoungeVisit.brand_id == brand_id)
        .group_by(LoungeVisit.user_id)
        .order_by(_func.count(LoungeVisit.id).desc())
    )
    total = agg.count()
    rows = agg.offset(offset).limit(limit).all()

    items = []
    for row in rows:
        guest = db.query(User).filter(User.id == row.user_id).first()
        if not guest:
            continue
        loyalty_row = db.query(LoungeGuestLoyalty).filter(
            LoungeGuestLoyalty.brand_id == brand_id,
            LoungeGuestLoyalty.user_id == row.user_id,
        ).first()
        bonus_balance = (loyalty_row.bonus_balance or 0) if loyalty_row else 0
        avg_bill = (row.total_spent // row.visits_count) if row.visits_count else 0
        items.append(LoungeCrmRegularOut(
            user_id=row.user_id,
            username=guest.username or f"user_{row.user_id}",
            avatar_url=guest.avatar_url,
            visits_count=row.visits_count,
            total_spent=row.total_spent or 0,
            last_visit_at=row.last_visit_at,
            avg_bill=avg_bill,
            bonus_balance=bonus_balance,
        ))

    return LoungeCrmRegularsOut(items=items, total=total, limit=limit, offset=offset)


@app.get("/lounges/{brand_id}/crm/guests/{guest_user_id}", response_model=LoungeCrmGuestCardOut, tags=["crm"])
@limiter.limit("60/minute")
def lounge_crm_guest_card(
    request: Request,
    brand_id: str,
    guest_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full guest card with visit history. Owner-only. Requires tier >= pro."""
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")
    if not current_user.is_admin:
        require_tier(db, brand_id, "pro")

    guest = db.query(User).filter(User.id == guest_user_id).first()
    if not guest:
        raise HTTPException(404, "Guest not found")

    visits = (
        db.query(LoungeVisit)
        .filter(LoungeVisit.brand_id == brand_id, LoungeVisit.user_id == guest_user_id)
        .order_by(LoungeVisit.created_at.desc())
        .all()
    )

    if not visits:
        raise HTTPException(404, "No visits found for this guest at this lounge")

    visits_count = len(visits)
    total_spent = sum(v.bill_amount for v in visits)
    avg_bill = total_spent // visits_count if visits_count else 0
    last_visit_at = visits[0].created_at
    first_visit_at = visits[-1].created_at

    loyalty_card = db.query(LoungeGuestLoyalty).filter(
        LoungeGuestLoyalty.brand_id == brand_id,
        LoungeGuestLoyalty.user_id == guest_user_id,
    ).first()
    bonus_balance = (loyalty_card.bonus_balance or 0) if loyalty_card else 0

    recent_visits = [
        GuestVisitRowOut(
            id=v.id,
            bill_amount=v.bill_amount,
            bonus_awarded=v.bonus_awarded,
            created_at=v.created_at,
        )
        for v in visits[:20]
    ]

    # Privacy: flavor preferences only if share_flavors=True
    share_ok = getattr(guest, "share_flavors", True)
    favorite_brands: Optional[List[str]] = None
    if share_ok:
        ingredients = (
            db.query(MixIngredient.brand)
            .join(Mix, Mix.id == MixIngredient.mix_id)
            .filter(Mix.author_id == guest_user_id, MixIngredient.brand.isnot(None))
            .all()
        )
        from collections import Counter as _BrandCounter
        brand_counts = _BrandCounter(row.brand for row in ingredients if row.brand)
        favorite_brands = [b for b, _ in brand_counts.most_common(5)] if brand_counts else []

    # Last 3 mixes by this guest tagged to this lounge
    last_mixes_q = (
        db.query(Mix)
        .filter(Mix.author_id == guest_user_id, Mix.lounge_id == brand_id)
        .order_by(Mix.created_at.desc())
        .limit(3)
        .all()
    )
    last_mixes = [
        {"id": m.id, "name": m.name, "created_at": m.created_at.isoformat() if m.created_at else None}
        for m in last_mixes_q
    ]

    return LoungeCrmGuestCardOut(
        user_id=guest_user_id,
        username=guest.username or f"user_{guest_user_id}",
        avatar_url=guest.avatar_url,
        first_visit_at=first_visit_at,
        last_visit_at=last_visit_at,
        visits_count=visits_count,
        total_spent=total_spent,
        avg_bill=avg_bill,
        bonus_balance=bonus_balance,
        favorite_brands=favorite_brands,
        last_mixes=last_mixes,
        recent_visits=recent_visits,
    )


@app.get("/lounges/{brand_id}/crm/heatmap", response_model=LoungeCRMHeatmapOut, tags=["crm"])
@limiter.limit("60/minute")
def lounge_crm_heatmap(
    request: Request,
    brand_id: str,
    tz_offset_min: int = Query(0, ge=-720, le=840),
    days_back: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Visit heatmap matrix (dow × hour) for CRM calendar view. Owner-only. Requires tier >= pro."""
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")
    if not current_user.is_admin:
        require_tier(db, brand_id, "pro")

    since = datetime.utcnow() - timedelta(days=days_back)

    # Use raw SQL for efficient GROUP BY on date-shifted values to avoid
    # loading all visit rows into Python. tz_offset_min applied as interval.
    sql = sa_text("""
        SELECT
            EXTRACT(DOW FROM (created_at + CAST(:tz_interval AS INTERVAL)))::int AS dow,
            EXTRACT(HOUR FROM (created_at + CAST(:tz_interval AS INTERVAL)))::int AS hour,
            COUNT(*)::int AS visit_count
        FROM lounge_visits
        WHERE brand_id = :brand_id
          AND created_at >= :since
        GROUP BY dow, hour
        ORDER BY dow, hour
    """)

    tz_interval = f"{tz_offset_min} minutes"
    rows = db.execute(sql, {
        "brand_id": brand_id,
        "since": since,
        "tz_interval": tz_interval,
    }).fetchall()

    cells = [
        LoungeCRMHeatmapCellOut(dow=row[0], hour=row[1], visit_count=row[2])
        for row in rows
    ]
    total_visits = sum(c.visit_count for c in cells)

    return LoungeCRMHeatmapOut(
        cells=cells,
        total_visits=total_visits,
        days_back=days_back,
        tz_offset_min=tz_offset_min,
    )


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


# ===================================================================
# BLOCK 1 — Bonus Redemption (2026-05-26)
# ===================================================================

def _compute_guest_balance(db: Session, brand_id: str, guest_user_id: int) -> dict:
    """Return per-lounge bonus stats for a guest.

    Source of truth: LoungeGuestLoyalty.bonus_balance (per-lounge wallet).
    total_earned / total_redeemed are audit aggregates for display only and
    are NOT used for balance decisions or validation.
    """
    loyalty = db.query(LoungeGuestLoyalty).filter(
        LoungeGuestLoyalty.brand_id == brand_id,
        LoungeGuestLoyalty.user_id == guest_user_id,
    ).first()

    bonus_balance = (loyalty.bonus_balance or 0) if loyalty else 0
    last_visit_at = loyalty.last_visit_at if loyalty else None

    # Audit aggregates (display only — not authoritative).
    total_earned = db.query(
        func.coalesce(func.sum(LoungeVisit.bonus_awarded), 0)
    ).filter(
        LoungeVisit.brand_id == brand_id,
        LoungeVisit.user_id == guest_user_id,
    ).scalar() or 0

    total_redeemed = db.query(
        func.coalesce(func.sum(BonusRedemption.bonus_points), 0)
    ).filter(
        BonusRedemption.brand_id == brand_id,
        BonusRedemption.guest_user_id == guest_user_id,
    ).scalar() or 0

    return {
        "total_earned": total_earned,
        "total_redeemed": total_redeemed,
        "bonus_balance": bonus_balance,
        "last_visit_at": last_visit_at,
    }


@app.get(
    "/lounges/{brand_id}/guests/{user_id}/balance",
    response_model=GuestBalanceOut,
    tags=["loyalty"],
)
def get_guest_bonus_balance(
    brand_id: str,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Текущий бонусный баланс гостя в конкретном лаунже (только для менеджера)."""
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Нет доступа к этому лаунжу")

    guest = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not guest:
        raise HTTPException(404, "Гость не найден")

    stats = _compute_guest_balance(db, brand_id, user_id)

    return GuestBalanceOut(
        user_id=guest.id,
        username=guest.username or guest.display_name or f"user_{guest.id}",
        avatar_url=guest.avatar_url,
        bonus_balance=stats["bonus_balance"],
        rub_equivalent=stats["bonus_balance"] // 10,
        total_earned=stats["total_earned"],
        total_redeemed=stats["total_redeemed"],
        last_visit_at=stats["last_visit_at"],
    )


@app.post(
    "/lounges/{brand_id}/redeem",
    response_model=GuestBalanceOut,
    tags=["loyalty"],
)
def redeem_bonus(
    brand_id: str,
    payload: RedeemIn,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Списание бонусов гостя владельцем/менеджером лаунжа."""
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Нет доступа к этому лаунжу")

    if payload.amount_rub < 200:
        raise HTTPException(400, "Минимальная сумма списания 200 ₽")

    guest = db.query(User).filter(
        User.id == payload.guest_user_id,
        User.is_deleted == False,
    ).first()
    if not guest:
        raise HTTPException(404, "Гость не найден")

    # Load loyalty row — source of truth for per-lounge balance.
    loyalty = db.query(LoungeGuestLoyalty).filter(
        LoungeGuestLoyalty.brand_id == brand_id,
        LoungeGuestLoyalty.user_id == payload.guest_user_id,
    ).first()
    bonus_balance = (loyalty.bonus_balance or 0) if loyalty else 0
    points_needed = payload.amount_rub * 10

    if bonus_balance < points_needed:
        available_rub = bonus_balance // 10
        raise HTTPException(
            400,
            f"Недостаточно баллов. Доступно: {available_rub} ₽",
        )

    balance_after = bonus_balance - points_needed

    # Deduct from the per-lounge wallet.
    if loyalty:
        loyalty.bonus_balance = balance_after

    redemption = BonusRedemption(
        brand_id=brand_id,
        guest_user_id=payload.guest_user_id,
        owner_user_id=current_user.id,
        amount_rub=payload.amount_rub,
        bonus_points=points_needed,
        balance_after=balance_after,
        note=payload.note,
    )
    db.add(redemption)
    db.commit()

    # Audit aggregates for the response (display only).
    stats = _compute_guest_balance(db, brand_id, payload.guest_user_id)
    return GuestBalanceOut(
        user_id=guest.id,
        username=guest.username or guest.display_name or f"user_{guest.id}",
        avatar_url=guest.avatar_url,
        bonus_balance=balance_after,
        rub_equivalent=balance_after // 10,
        total_earned=stats["total_earned"],
        total_redeemed=stats["total_redeemed"],
        last_visit_at=stats["last_visit_at"],
    )


@app.get(
    "/lounges/{brand_id}/redemptions",
    response_model=RedemptionListOut,
    tags=["loyalty"],
)
def list_redemptions(
    brand_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Лента списаний бонусов для аудита (только менеджер)."""
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Нет доступа к этому лаунжу")

    q = db.query(BonusRedemption).filter(BonusRedemption.brand_id == brand_id)
    total = q.count()
    rows = q.order_by(BonusRedemption.created_at.desc()).offset(offset).limit(limit).all()

    # resolve guest usernames in one pass
    guest_ids = list({r.guest_user_id for r in rows})
    users_map = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(guest_ids)).all()
    } if guest_ids else {}

    items = [
        RedemptionRowOut(
            id=r.id,
            brand_id=r.brand_id,
            guest_user_id=r.guest_user_id,
            guest_username=(
                users_map.get(r.guest_user_id, None).username
                if users_map.get(r.guest_user_id) else None
            ),
            owner_user_id=r.owner_user_id,
            amount_rub=r.amount_rub,
            bonus_points=r.bonus_points,
            balance_after=r.balance_after,
            note=r.note,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return RedemptionListOut(items=items, total=total)


# ===================================================================
# BLOCK 2 — Featured Promoted Slots (2026-05-26)
# ===================================================================

@app.get(
    "/lounges/promoted",
    response_model=PromotedListOut,
    tags=["lounges"],
)
def list_promoted_lounges(
    region: Optional[str] = Query(None, description="Фильтр по региону: 'moscow', 'spb', ..."),
    db: Session = Depends(get_db),
):
    """Публичный список активных featured-лаунжей (now between starts_at и ends_at)."""
    now = datetime.utcnow()
    q = db.query(LoungePromotedSlot).filter(
        LoungePromotedSlot.starts_at <= now,
        LoungePromotedSlot.ends_at >= now,
    )
    if region:
        q = q.filter(
            (LoungePromotedSlot.region == region) | (LoungePromotedSlot.region == None)
        )

    rows = q.order_by(LoungePromotedSlot.starts_at.asc()).all()

    items = [
        PromotedLoungeOut(
            brand_id=r.brand_id,
            starts_at=r.starts_at,
            ends_at=r.ends_at,
            region=r.region,
        )
        for r in rows
    ]
    return PromotedListOut(items=items, total=len(items))


@app.post(
    "/admin/promoted",
    response_model=PromotedLoungeOut,
    tags=["admin"],
)
def create_promoted_slot(
    payload: PromotedSlotIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Создать или обновить featured-слот для лаунжа (только admin)."""
    if payload.starts_at >= payload.ends_at:
        raise HTTPException(400, "starts_at должен быть раньше ends_at")

    existing = db.query(LoungePromotedSlot).filter(
        LoungePromotedSlot.brand_id == payload.brand_id
    ).first()

    if existing:
        existing.starts_at = payload.starts_at
        existing.ends_at = payload.ends_at
        existing.region = payload.region
        slot = existing
    else:
        slot = LoungePromotedSlot(
            brand_id=payload.brand_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            region=payload.region,
        )
        db.add(slot)

    db.commit()
    db.refresh(slot)

    return PromotedLoungeOut(
        brand_id=slot.brand_id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        region=slot.region,
    )


@app.post(
    "/admin/lounges/{brand_id}/featured",
    response_model=FeaturedSlotOut,
    tags=["admin"],
    status_code=201,
)
def create_featured_slot(
    brand_id: str,
    payload: FeaturedSlotIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Admin: создать featured-слот для лаунжа.
    Требует tier >= pro у лаунжа (lounge_billing_subscriptions).
    Для hero: проверяет конфликт по city на тот же период → 409.
    """
    # Check billing tier >= pro
    tier = get_active_tier(db, brand_id)
    from app.services.subscriptions import _tier_rank
    if _tier_rank(tier) < _tier_rank("pro"):
        raise HTTPException(
            status_code=402,
            detail=f"Лаунж {brand_id} имеет тариф '{tier}'. Для featured-слотов требуется pro+.",
        )

    now = datetime.utcnow()
    starts_at = now
    expires_at = now + timedelta(days=payload.days)

    # Hero conflict check
    if payload.slot_type == "hero":
        conflict = db.query(FeaturedSlot).filter(
            FeaturedSlot.slot_type == "hero",
            FeaturedSlot.city == payload.city,
            FeaturedSlot.status == "active",
            FeaturedSlot.expires_at > now,
        ).first()
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Hero-слот для города '{payload.city}' уже занят брендом '{conflict.brand_id}' до {conflict.expires_at.isoformat()}.",
            )

    slot = FeaturedSlot(
        brand_id=brand_id,
        slot_type=payload.slot_type,
        city=payload.city,
        starts_at=starts_at,
        expires_at=expires_at,
        price_paid=payload.price_paid,
        status="active",
        payment_method=payload.payment_method,
        created_by_admin=True,
        created_at=now,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)

    remaining = max(0, (slot.expires_at - now).days)
    return FeaturedSlotOut(
        id=slot.id,
        brand_id=slot.brand_id,
        slot_type=slot.slot_type,
        city=slot.city,
        starts_at=slot.starts_at,
        expires_at=slot.expires_at,
        price_paid=slot.price_paid or 0,
        status=slot.status,
        payment_method=slot.payment_method,
        created_by_admin=slot.created_by_admin or False,
        created_at=slot.created_at,
        remaining_days=remaining,
    )


@app.get(
    "/admin/featured",
    tags=["admin"],
)
def list_featured_slots(
    status: Optional[str] = Query("active", description="active | expired | cancelled"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: список всех featured-слотов с оставшимися днями."""
    now = datetime.utcnow()
    q = db.query(FeaturedSlot)
    if status:
        q = q.filter(FeaturedSlot.status == status)
    rows = q.order_by(FeaturedSlot.expires_at.desc()).all()

    result = []
    for r in rows:
        remaining = max(0, (r.expires_at - now).days)
        result.append({
            "id": r.id,
            "brand_id": r.brand_id,
            "slot_type": r.slot_type,
            "city": r.city,
            "starts_at": r.starts_at.isoformat() if r.starts_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "price_paid": r.price_paid or 0,
            "status": r.status,
            "payment_method": r.payment_method,
            "created_by_admin": r.created_by_admin or False,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "remaining_days": remaining,
        })
    return {"items": result, "total": len(result)}


@app.post(
    "/admin/featured/{slot_id}/cancel",
    tags=["admin"],
)
def cancel_featured_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: отменить featured-слот (для refund/досрочного завершения)."""
    slot = db.query(FeaturedSlot).filter(FeaturedSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Слот не найден")
    if slot.status == "cancelled":
        raise HTTPException(status_code=400, detail="Слот уже отменён")
    slot.status = "cancelled"
    db.commit()
    return {"ok": True, "slot_id": slot_id, "status": "cancelled"}


# ===================================================================
# BLOCK 3 — Brand Analytics (B2B data API, 2026-05-26)
# ===================================================================

@app.get(
    "/admin/brand-analytics",
    response_model=BrandAnalyticsOut,
    tags=["admin"],
)
def get_brand_analytics(
    brand: str = Query(..., description="Название бренда, напр. BlackBurn"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Агрегированная B2B аналитика для табачного бренда. Никаких персональных данных."""
    now = datetime.utcnow()
    period_30d_start = now - timedelta(days=30)
    period_60d_start = now - timedelta(days=60)

    # Total mixes using this brand
    total_mixes_using = db.query(func.count(func.distinct(MixIngredient.mix_id))).filter(
        func.lower(MixIngredient.brand) == brand.lower()
    ).scalar() or 0

    # Total likes on those mixes
    mix_ids_subq = db.query(MixIngredient.mix_id).filter(
        func.lower(MixIngredient.brand) == brand.lower()
    ).subquery()

    total_likes_on_those_mixes = db.query(func.count(Favorite.id)).filter(
        Favorite.mix_id.in_(mix_ids_subq)
    ).scalar() or 0

    # Unique authors
    unique_authors = db.query(func.count(func.distinct(Mix.author_id))).join(
        MixIngredient, Mix.id == MixIngredient.mix_id
    ).filter(
        func.lower(MixIngredient.brand) == brand.lower()
    ).scalar() or 0

    # Top-10 flavors by mixes count
    flavor_rows = db.query(
        MixIngredient.flavor,
        func.count(MixIngredient.mix_id).label("mixes_count"),
        func.avg(MixIngredient.percentage).label("avg_percentage"),
    ).filter(
        func.lower(MixIngredient.brand) == brand.lower(),
        MixIngredient.flavor != None,
    ).group_by(
        MixIngredient.flavor
    ).order_by(
        func.count(MixIngredient.mix_id).desc()
    ).limit(10).all()

    top_flavors = [
        FlavorPopularity(
            flavor=row.flavor,
            mixes_count=row.mixes_count,
            avg_percentage=round(float(row.avg_percentage or 0), 1),
        )
        for row in flavor_rows
    ]

    # Growth 30d vs previous 30d
    mixes_last_30d = db.query(func.count(func.distinct(MixIngredient.mix_id))).join(
        Mix, Mix.id == MixIngredient.mix_id
    ).filter(
        func.lower(MixIngredient.brand) == brand.lower(),
        Mix.created_at >= period_30d_start,
    ).scalar() or 0

    mixes_prev_30d = db.query(func.count(func.distinct(MixIngredient.mix_id))).join(
        Mix, Mix.id == MixIngredient.mix_id
    ).filter(
        func.lower(MixIngredient.brand) == brand.lower(),
        Mix.created_at >= period_60d_start,
        Mix.created_at < period_30d_start,
    ).scalar() or 0

    if mixes_prev_30d > 0:
        growth_30d = round((mixes_last_30d - mixes_prev_30d) / mixes_prev_30d * 100, 1)
    elif mixes_last_30d > 0:
        growth_30d = 100.0
    else:
        growth_30d = 0.0

    # Region split — group by lounge_id of mixes
    region_rows = db.query(
        Mix.lounge_id,
        func.count(func.distinct(Mix.id)).label("cnt"),
    ).join(
        MixIngredient, Mix.id == MixIngredient.mix_id
    ).filter(
        func.lower(MixIngredient.brand) == brand.lower(),
        Mix.lounge_id != None,
    ).group_by(
        Mix.lounge_id
    ).order_by(
        func.count(func.distinct(Mix.id)).desc()
    ).all()

    region_split = [
        RegionBucket(region=row.lounge_id, mixes_count=row.cnt)
        for row in region_rows
    ]

    return BrandAnalyticsOut(
        brand=brand,
        total_mixes_using=total_mixes_using,
        total_likes_on_those_mixes=total_likes_on_those_mixes,
        unique_authors=unique_authors,
        top_flavors=top_flavors,
        growth_30d=growth_30d,
        region_split=region_split,
    )


# -------------------------------------------------------------------
# ADMIN CRM — Lounge tier + badges management (2026-05-26)
# All mutating endpoints require is_admin == True.
# -------------------------------------------------------------------

def _meta_for_brand(brand_id: str, db: Session) -> LoungeAdminMeta:
    """Return existing LoungeAdminMeta row or a transient default (not flushed)."""
    meta = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if meta is None:
        meta = LoungeAdminMeta(brand_id=brand_id, tier="start", badges=[])
    return meta


def _list_item_for_brand(brand_id: str, db: Session) -> LoungeAdminListItemOut:
    meta = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    tier = meta.tier if meta else "start"
    badges = (meta.badges if isinstance(meta.badges, list) else []) if meta else []

    cutoff = datetime.utcnow() - timedelta(days=30)
    visits_last_30d = db.query(func.count(LoungeVisit.id)).filter(
        LoungeVisit.brand_id == brand_id,
        LoungeVisit.created_at >= cutoff,
    ).scalar() or 0

    bonus_outstanding = db.query(func.coalesce(func.sum(LoungeGuestLoyalty.bonus_balance), 0)).filter(
        LoungeGuestLoyalty.brand_id == brand_id,
    ).scalar() or 0

    promos_active = db.query(func.count(LoungePromo.id)).filter(
        LoungePromo.brand_id == brand_id,
        LoungePromo.active == True,
    ).scalar() or 0

    return LoungeAdminListItemOut(
        brand_id=brand_id,
        tier=tier,
        badges=badges,
        visits_last_30d=visits_last_30d,
        bonus_outstanding=int(bonus_outstanding),
        promos_active=promos_active,
    )


@app.get("/admin/lounges", response_model=List[LoungeAdminListItemOut], tags=["admin"])
def admin_list_lounges(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """List all known lounge brand_ids with tier, badges and aggregate stats."""
    brand_ids: set = set()
    for row in db.query(LoungeLoyaltyProgram.brand_id).all():
        brand_ids.add(row.brand_id)
    for row in db.query(LoungeVisit.brand_id).distinct().all():
        brand_ids.add(row.brand_id)
    for row in db.query(LoungeGuestLoyalty.brand_id).distinct().all():
        brand_ids.add(row.brand_id)
    for row in db.query(LoungeAdminMeta.brand_id).all():
        brand_ids.add(row.brand_id)

    result = [_list_item_for_brand(bid, db) for bid in sorted(brand_ids)]
    return result


@app.get("/admin/lounges/{brand_id}", response_model=LoungeAdminMetaOut, tags=["admin"])
def admin_get_lounge(
    brand_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Return full admin meta (including notes) for a single lounge."""
    meta = _meta_for_brand(brand_id, db)
    return LoungeAdminMetaOut(
        brand_id=brand_id,
        tier=meta.tier,
        badges=meta.badges if isinstance(meta.badges, list) else [],
        notes=meta.notes,
    )


@app.patch("/admin/lounges/{brand_id}", response_model=LoungeAdminMetaOut, tags=["admin"])
def admin_patch_lounge(
    brand_id: str,
    payload: LoungeAdminMetaIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Update tier / badges / notes for a lounge. Creates the row if absent."""
    if payload.tier is not None and payload.tier not in VALID_LOUNGE_TIERS:
        raise HTTPException(status_code=422, detail=f"Invalid tier. Valid values: {sorted(VALID_LOUNGE_TIERS)}")
    if payload.badges is not None:
        invalid = set(payload.badges) - VALID_LOUNGE_BADGES
        if invalid:
            raise HTTPException(status_code=422, detail=f"Invalid badges: {invalid}. Valid: {sorted(VALID_LOUNGE_BADGES)}")

    meta = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if meta is None:
        meta = LoungeAdminMeta(brand_id=brand_id, tier="start", badges=[])
        db.add(meta)

    if payload.tier is not None:
        meta.tier = payload.tier
    if payload.badges is not None:
        meta.badges = list(payload.badges)
    if payload.notes is not None:
        meta.notes = payload.notes
    meta.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(meta)

    return LoungeAdminMetaOut(
        brand_id=meta.brand_id,
        tier=meta.tier,
        badges=meta.badges if isinstance(meta.badges, list) else [],
        notes=meta.notes,
    )


@app.post("/admin/lounges/{brand_id}/badge/{badge_name}", response_model=LoungeAdminMetaOut, tags=["admin"])
def admin_add_badge(
    brand_id: str,
    badge_name: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Idempotently add a single badge to a lounge."""
    if badge_name not in VALID_LOUNGE_BADGES:
        raise HTTPException(status_code=422, detail=f"Invalid badge. Valid values: {sorted(VALID_LOUNGE_BADGES)}")

    meta = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if meta is None:
        meta = LoungeAdminMeta(brand_id=brand_id, tier="start", badges=[])
        db.add(meta)

    current = meta.badges if isinstance(meta.badges, list) else []
    if badge_name not in current:
        meta.badges = current + [badge_name]
        meta.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(meta)

    return LoungeAdminMetaOut(
        brand_id=meta.brand_id,
        tier=meta.tier,
        badges=meta.badges if isinstance(meta.badges, list) else [],
        notes=meta.notes,
    )


@app.delete("/admin/lounges/{brand_id}/badge/{badge_name}", response_model=LoungeAdminMetaOut, tags=["admin"])
def admin_remove_badge(
    brand_id: str,
    badge_name: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Remove a badge from a lounge (no-op if badge not present)."""
    meta = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if meta is None:
        raise HTTPException(status_code=404, detail="Lounge not found in admin meta")

    current = meta.badges if isinstance(meta.badges, list) else []
    updated = [b for b in current if b != badge_name]
    if len(updated) != len(current):
        meta.badges = updated
        meta.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(meta)

    return LoungeAdminMetaOut(
        brand_id=meta.brand_id,
        tier=meta.tier,
        badges=meta.badges if isinstance(meta.badges, list) else [],
        notes=meta.notes,
    )


# -------------------------------------------------------------------
# PUBLIC — lounge admin-meta (no auth, for MixCard / lounge profile)
# -------------------------------------------------------------------

@app.get("/lounges/{brand_id}/admin-meta", response_model=LoungePublicMetaOut, tags=["lounges"])
def get_lounge_public_meta(brand_id: str, db: Session = Depends(get_db)):
    """Public endpoint: returns tier and badges for a lounge. No auth required."""
    meta = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if meta is None:
        return LoungePublicMetaOut(brand_id=brand_id, tier="start", badges=[])
    return LoungePublicMetaOut(
        brand_id=meta.brand_id,
        tier=meta.tier,
        badges=meta.badges if isinstance(meta.badges, list) else [],
    )


@app.get("/lounges/{brand_id}/public-meta", response_model=LoungePublicMetaOut, tags=["lounges"])
def get_lounge_public_meta_v2(brand_id: str, db: Session = Depends(get_db)):
    """
    Public endpoint (no auth): full social-proof meta for iOS LoungeProfileView.

    Returns active billing tier via get_active_tier(), public badges from
    lounge_admin_meta, subscription_active flag, and is_featured_now
    (active featured_slot for this brand).
    """
    # Tier from billing (overrides admin_meta.tier for display)
    active_tier = get_active_tier(db, brand_id)

    # Badges from admin CRM meta
    meta = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    badges: list = meta.badges if (meta and isinstance(meta.badges, list)) else []

    # subscription_active: any row with status active|trialing and expires_at > now
    from app.models import LoungeBillingSubscription
    now = datetime.utcnow()
    sub_active = (
        db.query(LoungeBillingSubscription.id)
        .filter(
            LoungeBillingSubscription.brand_id == brand_id,
            LoungeBillingSubscription.expires_at > now,
            LoungeBillingSubscription.status.in_(["active", "trialing"]),
        )
        .first()
    ) is not None

    # is_featured_now: active featured slot for this brand
    featured = (
        db.query(FeaturedSlot.id)
        .filter(
            FeaturedSlot.brand_id == brand_id,
            FeaturedSlot.status == "active",
            FeaturedSlot.expires_at > now,
        )
        .first()
    ) is not None

    return LoungePublicMetaOut(
        brand_id=brand_id,
        tier=active_tier,
        badges=badges,
        subscription_active=sub_active,
        is_featured_now=featured,
    )


# -------------------------------------------------------------------
# BILLING SUBSCRIPTIONS — Sprint 1, 2026-05-27
# -------------------------------------------------------------------

@app.post(
    "/admin/lounges/{brand_id}/subscription",
    response_model=LoungeBillingSubscriptionOut,
    tags=["admin", "billing"],
)
def admin_grant_subscription(
    brand_id: str,
    payload: LoungeBillingSubscriptionGrantIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Admin: grant or extend a billing subscription for a lounge.

    Creates a new row in lounge_billing_subscriptions. Duration starts
    from now (or from current active expires_at, whichever is later),
    so calling multiple times extends the subscription rather than
    overwriting.

    Example:
        POST /admin/lounges/garden_lounge_korolev/subscription
        {"tier": "pro", "days": 90, "payment_method": "trial"}
    """
    if payload.tier not in VALID_LOUNGE_TIERS:
        raise HTTPException(422, f"Invalid tier. Valid: {sorted(VALID_LOUNGE_TIERS)}")
    if payload.days <= 0:
        raise HTTPException(422, "days must be > 0")

    now = datetime.utcnow()

    # If there's already an active subscription, extend from its expires_at
    existing = (
        db.query(LoungeBillingSubscription)
        .filter(
            LoungeBillingSubscription.brand_id == brand_id,
            LoungeBillingSubscription.expires_at > now,
            LoungeBillingSubscription.status.in_(["active", "trialing"]),
        )
        .order_by(LoungeBillingSubscription.expires_at.desc())
        .first()
    )

    start_from = existing.expires_at if existing else now
    new_expires = start_from + timedelta(days=payload.days)

    status = "trialing" if payload.payment_method == "trial" else "active"

    sub = LoungeBillingSubscription(
        brand_id=brand_id,
        tier=payload.tier,
        status=status,
        started_at=now,
        expires_at=new_expires,
        payment_method=payload.payment_method,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    return LoungeBillingSubscriptionOut(
        id=sub.id,
        brand_id=sub.brand_id,
        tier=sub.tier,
        status=sub.status,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
        payment_method=sub.payment_method,
        external_id=sub.external_id,
        created_at=sub.created_at,
    )


@app.get(
    "/admin/lounges/{brand_id}/subscription",
    response_model=List[LoungeBillingSubscriptionOut],
    tags=["admin", "billing"],
)
def admin_list_subscriptions(
    brand_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: list all billing subscription rows for a lounge (history + active)."""
    rows = (
        db.query(LoungeBillingSubscription)
        .filter(LoungeBillingSubscription.brand_id == brand_id)
        .order_by(LoungeBillingSubscription.expires_at.desc())
        .all()
    )
    return [
        LoungeBillingSubscriptionOut(
            id=r.id,
            brand_id=r.brand_id,
            tier=r.tier,
            status=r.status,
            started_at=r.started_at,
            expires_at=r.expires_at,
            payment_method=r.payment_method,
            external_id=r.external_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


# -------------------------------------------------------------------
# YOOKASSA STUB ENDPOINTS — Sprint 1 (real integration in Sprint 2)
# -------------------------------------------------------------------

@app.post(
    "/lounges/{brand_id}/subscription/checkout",
    response_model=LoungeCheckoutOut,
    tags=["billing"],
)
def lounge_subscription_checkout(
    brand_id: str,
    payload: LoungeCheckoutIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    STUB: Returns a YooKassa checkout URL for a lounge subscription.
    Full YooKassa SDK integration is planned for Sprint 2.
    Currently returns a placeholder URL.
    """
    current_user = get_required_user(user)
    if not can_manage_brand(current_user, brand_id):
        raise HTTPException(403, "Business access required")

    if payload.tier not in VALID_LOUNGE_TIERS:
        raise HTTPException(422, f"Invalid tier. Valid: {sorted(VALID_LOUNGE_TIERS)}")

    # STUB — Sprint 2 will call yookassa SDK here
    fake_payment_id = str(uuid.uuid4())
    checkout_url = f"https://yookassa.ru/checkout/{fake_payment_id}"

    return LoungeCheckoutOut(checkout_url=checkout_url)


@app.post(
    "/webhooks/yookassa",
    response_model=StatusOut,
    tags=["billing"],
)
async def yookassa_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    STUB: YooKassa payment webhook receiver.

    Full HMAC validation and payment processing will be implemented in Sprint 2.
    Currently logs the payload and returns 200 to prevent YooKassa retries.

    Expected payload:
        {"type": "notification", "event": "payment.succeeded",
         "object": {"id": "...", "metadata": {"brand_id": "...", "tier": "..."}}}
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    # STUB — Sprint 2 will:
    # 1. Validate HMAC-SHA256 signature from X-Content-SHA256 header
    # 2. Parse payment.succeeded event
    # 3. Extract brand_id + tier from payment.metadata
    # 4. Create LoungeBillingSubscription row (30 days, status=active)

    import logging as _lg
    _lg.getLogger(__name__).info(
        "yookassa_webhook stub received event=%s",
        body.get("event", "unknown"),
    )


# ===================================================================
# ADMIN WEB CRM — /admin-web/*
# Server-rendered HTML UI (Jinja2 + HTMX).
# Auth: session cookie "admin_session" = JWT access token for an
# is_admin user. Completely separate from /admin/* JSON endpoints.
# ===================================================================

_ADMIN_SESSION_COOKIE = "ember_admin_session"
_ADMIN_SESSION_MAX_AGE = 60 * 60 * 8  # 8 hours


def _admin_web_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """
    Reads admin_session cookie, validates JWT, returns User if is_admin.
    Returns None if not authenticated.
    """
    token = request.cookies.get(_ADMIN_SESSION_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        return None
    user = db.query(User).get(user_id)
    if not user:
        return None
    if user.is_banned or getattr(user, "is_deleted", False):
        return None
    if not user.is_admin and user.id != 1:
        return None
    return user


def _require_admin_web(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency for admin-web routes: redirect to login if not authenticated."""
    user = _admin_web_user(request, db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/admin-web/login"})
    return user


def _fmt_dt(dt) -> str:
    """Format datetime for display."""
    if dt is None:
        return "—"
    try:
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(dt)


def _sub_status_for_brand(brand_id: str, db: Session):
    """Return (status, expires_at_str) for the active subscription of a brand."""
    now = datetime.utcnow()
    sub = (
        db.query(LoungeBillingSubscription)
        .filter(
            LoungeBillingSubscription.brand_id == brand_id,
            LoungeBillingSubscription.expires_at > now,
            LoungeBillingSubscription.status.in_(["active", "trialing"]),
        )
        .order_by(LoungeBillingSubscription.expires_at.desc())
        .first()
    )
    if sub:
        return sub.status, _fmt_dt(sub.expires_at)
    return None, None


# ---------------------------------------------------------------
# GET /admin-web/login
# ---------------------------------------------------------------
@app.get("/admin-web/login", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


# ---------------------------------------------------------------
# POST /admin-web/login
# ---------------------------------------------------------------
@app.post("/admin-web/login", response_class=HTMLResponse, tags=["admin-web"])
async def admin_web_login_submit(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    email_val = (form.get("email") or "").strip().lower()
    password_val = (form.get("password") or "").strip()

    def _render_error(msg: str):
        return templates.TemplateResponse(request, "login.html", {"error": msg})

    if not email_val or not password_val:
        return _render_error("Введите email и пароль")

    user = db.query(User).filter(
        func.lower(User.email) == email_val
    ).first()

    if not user:
        return _render_error("Неверный email или пароль")
    if not verify_password(password_val, user.password_hash):
        return _render_error("Неверный email или пароль")
    if not user.is_admin and user.id != 1:
        return _render_error("Нет прав администратора")

    # create_access_token uses fixed ACCESS_TOKEN_EXPIRE_MINUTES (7 days), which is fine.
    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse(url="/admin-web/", status_code=302)
    response.set_cookie(
        _ADMIN_SESSION_COOKIE,
        token,
        max_age=_ADMIN_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


# ---------------------------------------------------------------
# GET /admin-web/logout
# ---------------------------------------------------------------
@app.get("/admin-web/logout", tags=["admin-web"])
def admin_web_logout():
    response = RedirectResponse(url="/admin-web/login", status_code=302)
    response.delete_cookie(_ADMIN_SESSION_COOKIE)
    return response


# ---------------------------------------------------------------
# GET /admin-web/   (dashboard)
# ---------------------------------------------------------------
@app.get("/admin-web/", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    flash_ok: str = Query(default=None),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    now = datetime.utcnow()
    cutoff_30 = now - timedelta(days=30)

    total_users = db.query(func.count(User.id)).scalar() or 0
    banned_users = db.query(func.count(User.id)).filter(User.is_banned.is_(True)).scalar() or 0
    total_mixes = db.query(func.count(Mix.id)).scalar() or 0

    # MAU: users who have any UserActivity in last 30 days
    mau = (
        db.query(func.count(func.distinct(UserActivity.user_id)))
        .filter(UserActivity.created_at >= cutoff_30)
        .scalar() or 0
    )

    # Distinct lounges
    brand_ids_set: set = set()
    for row in db.query(LoungeGuestLoyalty.brand_id).distinct().all():
        brand_ids_set.add(row.brand_id)
    for row in db.query(LoungeVisit.brand_id).distinct().all():
        brand_ids_set.add(row.brand_id)
    for row in db.query(LoungeAdminMeta.brand_id).all():
        brand_ids_set.add(row.brand_id)
    total_lounges = len(brand_ids_set)

    # Active subscriptions
    active_subs = (
        db.query(func.count(LoungeBillingSubscription.id))
        .filter(
            LoungeBillingSubscription.expires_at > now,
            LoungeBillingSubscription.status.in_(["active", "trialing"]),
        )
        .scalar() or 0
    )

    # Top 5 lounges by visits_30d
    top_rows = (
        db.query(LoungeVisit.brand_id, func.count(LoungeVisit.id).label("cnt"))
        .filter(LoungeVisit.created_at >= cutoff_30)
        .group_by(LoungeVisit.brand_id)
        .order_by(func.count(LoungeVisit.id).desc())
        .limit(5)
        .all()
    )
    top_lounges = []
    for brand_id, cnt in top_rows:
        meta_row = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
        tier = meta_row.tier if meta_row else "start"
        sub_status, _ = _sub_status_for_brand(brand_id, db)
        top_lounges.append({
            "brand_id": brand_id,
            "visits_30d": cnt,
            "tier": tier,
            "sub_status": sub_status,
        })

    # Recent 10 users
    recent_users_rows = (
        db.query(User)
        .filter(User.is_deleted.is_(False))
        .order_by(User.id.desc())
        .limit(10)
        .all()
    )
    recent_users = [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "created_at": _fmt_dt(getattr(u, "created_at", None)),
            "is_banned": u.is_banned,
            "is_admin": u.is_admin,
        }
        for u in recent_users_rows
    ]

    ctx = {
        "active_nav": "dashboard",
        "admin_email": admin.email,
        "flash_ok": flash_ok,
        "stats": {
            "total_users": total_users,
            "mau": mau,
            "total_lounges": total_lounges,
            "active_subscriptions": active_subs,
            "banned_users": banned_users,
            "total_mixes": total_mixes,
        },
        "top_lounges": top_lounges,
        "recent_users": recent_users,
    }
    return templates.TemplateResponse(request, "dashboard.html", ctx)


# ---------------------------------------------------------------
# GET /admin-web/users
# ---------------------------------------------------------------
@app.get("/admin-web/users", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_users(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    q: str = Query(default=None),
    flash_ok: str = Query(default=None),
    flash_err: str = Query(default=None),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    per_page = 50
    base_q = db.query(User).filter(User.is_deleted.is_(False))
    if q:
        pattern = f"%{q.strip()}%"
        base_q = base_q.filter(
            (User.email.ilike(pattern)) | (User.username.ilike(pattern))
        )

    total = base_q.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    rows = (
        base_q.order_by(User.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    users_out = []
    for u in rows:
        total_visits = (
            db.query(func.count(LoungeVisit.id))
            .filter(LoungeVisit.user_id == u.id)
            .scalar() or 0
        )
        prog = db.query(UserProgress).filter(UserProgress.user_id == u.id).first()
        total_points = prog.points if prog else 0

        users_out.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "created_at": _fmt_dt(getattr(u, "created_at", None)),
            "is_banned": u.is_banned,
            "is_admin": u.is_admin,
            "account_type": u.account_type,
            "total_visits": total_visits,
            "total_points": total_points,
        })

    ctx = {
        "active_nav": "users",
        "admin_email": admin.email,
        "users": users_out,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "query": q,
        "flash_ok": flash_ok,
        "flash_err": flash_err,
    }
    return templates.TemplateResponse(request, "users.html", ctx)


# ---------------------------------------------------------------
# GET /admin-web/users/{user_id}
# ---------------------------------------------------------------
@app.get("/admin-web/users/{user_id}", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_user_detail(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    flash_ok: str = Query(default=None),
    flash_err: str = Query(default=None),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    u = db.query(User).get(user_id)
    if not u:
        raise HTTPException(404, "User not found")

    prog = db.query(UserProgress).filter(UserProgress.user_id == u.id).first()
    total_visits = (
        db.query(func.count(LoungeVisit.id)).filter(LoungeVisit.user_id == u.id).scalar() or 0
    )
    mixes_count = db.query(func.count(Mix.id)).filter(Mix.author_id == u.id).scalar() or 0
    favs_count = db.query(func.count(Favorite.id)).filter(Favorite.user_id == u.id).scalar() or 0
    followers_count = (
        db.query(func.count(UserFollow.id)).filter(UserFollow.following_id == u.id).scalar() or 0
    )
    following_count = (
        db.query(func.count(UserFollow.id)).filter(UserFollow.follower_id == u.id).scalar() or 0
    )
    device_tokens_count = (
        db.query(func.count(DeviceToken.id)).filter(DeviceToken.user_id == u.id).scalar() or 0
    )

    recent_visits = (
        db.query(LoungeVisit)
        .filter(LoungeVisit.user_id == u.id)
        .order_by(LoungeVisit.created_at.desc())
        .limit(20)
        .all()
    )
    visits_out = [
        {
            "brand_id": v.brand_id,
            "bill_amount": v.bill_amount,
            "bonus_awarded": v.bonus_awarded,
            "created_at": _fmt_dt(v.created_at),
        }
        for v in recent_visits
    ]

    user_dict = {
        "id": u.id,
        "email": u.email,
        "username": u.username,
        "display_name": u.display_name,
        "city": u.city,
        "account_type": u.account_type,
        "is_admin": u.is_admin,
        "is_banned": u.is_banned,
        "ban_reason": u.ban_reason,
        "banned_at": _fmt_dt(u.banned_at),
        "premium_until": _fmt_dt(u.premium_until),
        "ton_address": u.ton_address,
        "created_at": _fmt_dt(getattr(u, "created_at", None)),
        "points": prog.points if prog else 0,
        "rating": prog.rating if prog else 0,
        "streak_days": prog.streak_days if prog else 0,
        "mixes_count": mixes_count,
        "favorites_count": favs_count,
        "total_visits": total_visits,
        "followers_count": followers_count,
        "following_count": following_count,
        "device_tokens_count": device_tokens_count,
    }

    ctx = {
        "active_nav": "users",
        "admin_email": admin.email,
        "u": user_dict,
        "recent_visits": visits_out,
        "flash_ok": flash_ok,
        "flash_err": flash_err,
    }
    return templates.TemplateResponse(request, "user_detail.html", ctx)


# ---------------------------------------------------------------
# POST /admin-web/users/{user_id}/ban
# ---------------------------------------------------------------
@app.post("/admin-web/users/{user_id}/ban", tags=["admin-web"])
async def admin_web_ban_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    form = await request.form()
    reason = form.get("reason", "").strip() or "Нарушение правил платформы"

    u = db.query(User).get(user_id)
    if not u:
        return RedirectResponse(url="/admin-web/users?flash_err=User+not+found", status_code=302)
    if u.id == admin.id:
        return RedirectResponse(url=f"/admin-web/users/{user_id}?flash_err=Cannot+ban+yourself", status_code=302)

    u.is_banned = True
    u.ban_reason = reason
    u.banned_at = datetime.utcnow()
    db.commit()
    return RedirectResponse(url=f"/admin-web/users/{user_id}?flash_ok=User+banned", status_code=302)


# ---------------------------------------------------------------
# POST /admin-web/users/{user_id}/unban
# ---------------------------------------------------------------
@app.post("/admin-web/users/{user_id}/unban", tags=["admin-web"])
def admin_web_unban_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    u = db.query(User).get(user_id)
    if not u:
        return RedirectResponse(url="/admin-web/users?flash_err=User+not+found", status_code=302)

    u.is_banned = False
    u.ban_reason = None
    u.banned_at = None
    db.commit()
    return RedirectResponse(url=f"/admin-web/users/{user_id}?flash_ok=User+unbanned", status_code=302)


# ---------------------------------------------------------------
# GET /admin-web/lounges
# ---------------------------------------------------------------
@app.get("/admin-web/lounges", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_lounges(
    request: Request,
    db: Session = Depends(get_db),
    flash_ok: str = Query(default=None),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    brand_ids: set = set()
    for row in db.query(LoungeLoyaltyProgram.brand_id).all():
        brand_ids.add(row.brand_id)
    for row in db.query(LoungeVisit.brand_id).distinct().all():
        brand_ids.add(row.brand_id)
    for row in db.query(LoungeGuestLoyalty.brand_id).distinct().all():
        brand_ids.add(row.brand_id)
    for row in db.query(LoungeAdminMeta.brand_id).all():
        brand_ids.add(row.brand_id)

    cutoff_30 = datetime.utcnow() - timedelta(days=30)
    lounges_out = []
    for bid in sorted(brand_ids):
        meta_row = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == bid).first()
        tier = meta_row.tier if meta_row else "start"
        badges = (meta_row.badges if isinstance(meta_row.badges, list) else []) if meta_row else []

        visits_30d = (
            db.query(func.count(LoungeVisit.id))
            .filter(LoungeVisit.brand_id == bid, LoungeVisit.created_at >= cutoff_30)
            .scalar() or 0
        )
        bonus_outstanding = (
            db.query(func.coalesce(func.sum(LoungeGuestLoyalty.bonus_balance), 0))
            .filter(LoungeGuestLoyalty.brand_id == bid)
            .scalar() or 0
        )
        promos_active = (
            db.query(func.count(LoungePromo.id))
            .filter(LoungePromo.brand_id == bid, LoungePromo.active == True)
            .scalar() or 0
        )
        sub_status, sub_expires = _sub_status_for_brand(bid, db)

        lounges_out.append({
            "brand_id": bid,
            "tier": tier,
            "badges": badges,
            "visits_last_30d": visits_30d,
            "bonus_outstanding": int(bonus_outstanding),
            "promos_active": promos_active,
            "sub_status": sub_status,
            "sub_expires": sub_expires,
        })

    ctx = {
        "active_nav": "lounges",
        "admin_email": admin.email,
        "lounges": lounges_out,
        "flash_ok": flash_ok,
    }
    return templates.TemplateResponse(request, "lounges.html", ctx)


# ---------------------------------------------------------------
# LOUNGE ONBOARDING — Create / Parse (CRM)
# IMPORTANT: These routes must be registered BEFORE /lounges/{brand_id}
# so FastAPI matches /lounges/new literally (not as brand_id="new").
# GET  /admin-web/lounges/new      — form
# POST /admin-web/lounges/parse    — server-side URL parser
# POST /admin-web/lounges/new      — save to lounge_catalog + lounge_assets
# ---------------------------------------------------------------
def _slugify(text: str) -> str:
    """Convert a string to a brand_id-safe slug (lowercase ASCII + underscores)."""
    import unicodedata
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    return text[:60]


def _domain_slug(url: str) -> str:
    """Extract domain and turn it into a slug, e.g. hookahplace.ru → hookahplace."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc or url
        host = host.replace("www.", "")
        base = host.split(".")[0]
        return _slugify(base)
    except Exception:
        return "new_lounge"


def _download_image(url: str, dest_path: str) -> bool:
    """Download an image from url to dest_path. Returns True on success."""
    import urllib.request
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {"User-Agent": "Mozilla/5.0 (compatible; HookaBot/1.0)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read()
        if len(data) < 2048:          # skip tiny icons
            return False
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def _parse_lounge_url_internal(url: str) -> dict:
    """
    Fetch a lounge website and extract metadata.
    Returns a dict with keys: title, description, tagline, summary, address,
    phone, hours, venue_format, brand_id_suggestion, cover_url_remote,
    avatar_url_remote, extra_image_urls.
    All image fields are remote URLs (not yet downloaded).
    """
    import urllib.request
    import urllib.parse as _uparse
    import ssl
    import json as _json
    from html.parser import HTMLParser

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
        html_bytes = resp.read(500_000)
        final_url = resp.url

    try:
        html = html_bytes.decode("utf-8", errors="replace")
    except Exception:
        html = html_bytes.decode("cp1251", errors="replace")

    # Strip HTML to plain text (keep href attrs for tel: links)
    text_plain = re.sub(r"<[^>]+>", " ", html)
    text_plain = re.sub(r"[ \t]+", " ", text_plain)

    class MetaParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.title = ""
            self.description = ""
            self.og_image = ""
            self.og_title = ""
            self.og_description = ""
            self.images: list = []
            self.tel_hrefs: list = []  # href="tel:..." values
            self._in_title = False
            self._in_script = False
            self._script_type = ""
            self.ld_json_blocks: list = []
            self._script_buf = ""

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "title":
                self._in_title = True
            elif tag == "script":
                stype = (a.get("type") or "").lower()
                if stype == "application/ld+json":
                    self._in_script = True
                    self._script_type = "ldjson"
                    self._script_buf = ""
            elif tag == "meta":
                prop = (a.get("property") or a.get("name") or "").lower()
                content = a.get("content") or ""
                if prop == "og:title":
                    self.og_title = content
                elif prop == "og:description":
                    self.og_description = content
                elif prop == "og:image":
                    self.og_image = content
                elif prop in ("description",):
                    self.description = content
            elif tag == "img":
                src = a.get("src") or a.get("data-src") or ""
                if src and not src.startswith("data:"):
                    self.images.append(src)
            elif tag == "a":
                href = (a.get("href") or "").strip()
                if href.startswith("tel:"):
                    self.tel_hrefs.append(href[4:])

        def handle_data(self, data):
            if self._in_title:
                self.title += data
            if self._in_script and self._script_type == "ldjson":
                self._script_buf += data

        def handle_endtag(self, tag):
            if tag == "title":
                self._in_title = False
            if tag == "script" and self._in_script:
                self._in_script = False
                if self._script_buf.strip():
                    self.ld_json_blocks.append(self._script_buf.strip())
                self._script_buf = ""
                self._script_type = ""

    parser = MetaParser()
    parser.feed(html)

    title = (parser.og_title or parser.title or "").strip()
    description = (parser.og_description or parser.description or "").strip()

    # --- Phone ---
    # 1. Prefer tel: href links (most reliable)
    def _normalize_phone(raw: str) -> str:
        """Normalize to +7 XXX XXX-XX-XX format. Return '' if invalid."""
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 11 and digits[0] in ("7", "8"):
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits
        else:
            return ""
        return f"+{digits[0]} {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"

    phone = ""
    # Try tel: hrefs first
    for raw_tel in parser.tel_hrefs:
        candidate = _normalize_phone(raw_tel)
        if candidate:
            phone = candidate
            break

    # If no tel: href, scan text for RU phone patterns
    if not phone:
        # Scan near "тел"/"phone" keywords first, then whole text
        for search_area in [
            text_plain,
            html,
        ]:
            # Look for phone near keyword
            for m in re.finditer(
                r"(?:тел[еефон\.:\s]*|phone[\s:]*|☎|📞)[\s\(\+]*(\+?[78][\s\-\(\)0-9]{9,15})",
                search_area,
                re.IGNORECASE,
            ):
                candidate = _normalize_phone(m.group(1))
                if candidate:
                    phone = candidate
                    break
            if phone:
                break

    if not phone:
        # Fallback: any RU-looking phone sequence in text
        for m in re.finditer(
            r"(?<!\d)(\+?[78][\s\-\(\)]{0,2}[\(\[]?\d{3}[\)\]]?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})(?!\d)",
            text_plain,
        ):
            candidate = _normalize_phone(m.group(1))
            if candidate:
                phone = candidate
                break

    # --- Address ---
    # 1. Try JSON-LD schema.org PostalAddress
    address = ""
    for ld_block in parser.ld_json_blocks:
        try:
            ld = _json.loads(ld_block)
            # handle @graph arrays
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                if isinstance(item, dict):
                    graph = item.get("@graph", [])
                    items_inner = graph if graph else [item]
                    for node in items_inner:
                        if not isinstance(node, dict):
                            continue
                        addr_node = node.get("address") or {}
                        if isinstance(addr_node, str) and addr_node:
                            address = addr_node
                            break
                        if isinstance(addr_node, dict):
                            street = addr_node.get("streetAddress") or ""
                            locality = addr_node.get("addressLocality") or ""
                            parts = [p for p in [locality, street] if p]
                            if parts:
                                address = ", ".join(parts)
                                break
                    if address:
                        break
        except Exception:
            pass
        if address:
            break

    # 2. Regex on plain text — explicit street keyword required (word boundary safe)
    if not address:
        city_pat = (
            r"(?:Москва|Санкт-Петербург|СПб|Новосибирск|Екатеринбург|Казань|"
            r"Нижний\s+Новгород|Красноярск|Челябинск|Омск|Самара|Ростов-на-Дону|"
            r"Уфа|Краснодар|Пермь|Воронеж)"
        )
        # Street keyword must start at a word boundary to avoid matching mid-word
        street_pat = (
            r"(?:\bул\.\s*|\bулица\s+|\bпросп?\.\s*|\bпроспект\s+|\bпер\.\s*|"
            r"\bпереулок\s+|\bш\.\s*|\bшоссе\s+|\bбул\.\s*|\bбульвар\s+|"
            r"\bнаб\.\s*|\bнабережная\s+|\bпл\.\s*|\bплощадь\s+|\bаллея\s+)"
            r"[А-Яа-яЁё][А-Яа-яЁё\- ]{1,40},?\s*д?\.?\s*\d+"
        )
        # First: city + street
        m = re.search(
            rf"({city_pat})[,\s]{{1,20}}({street_pat})",
            text_plain,
            re.IGNORECASE,
        )
        if m:
            address = f"{m.group(1)}, {m.group(2)}"
            address = re.sub(r"\s+", " ", address).strip()
        else:
            # Just street pattern
            m = re.search(street_pat, text_plain, re.IGNORECASE)
            if m:
                # Try to find city name just before it (within 80 chars)
                start = max(0, m.start() - 80)
                prefix = text_plain[start:m.start()]
                city_m = re.search(city_pat, prefix, re.IGNORECASE)
                if city_m:
                    address = f"{city_m.group(0)}, {m.group(0)}"
                else:
                    address = m.group(0)
                address = re.sub(r"\s+", " ", address).strip()

    # 3. Bare StreetName, N pattern (Tilda/common sites like "Никитинская, 17")
    #    Strategy: find the phone number in original text (with punctuation), grab ±400 chars
    if not address and phone:
        phone_digits = re.sub(r"\D", "", phone)
        # Build a loose pattern from last 10 digits (allows spaces/dashes between)
        def _phone_search_pat(digits: str) -> str:
            # Escape and join with optional separators
            return r"[\s\-\(\)]*".join(re.escape(c) for c in digits[-10:])
        idx = -1
        pm = re.search(_phone_search_pat(phone_digits), text_plain)
        if pm:
            idx = pm.start()
        if idx >= 0:
            chunk = text_plain[max(0, idx - 300): idx + 400]
            city_pat_loc = (
                r"(?:Москва|Санкт-Петербург|СПб|Новосибирск|Екатеринбург|Казань|"
                r"Нижний\s+Новгород|Красноярск|Челябинск|Омск|Самара|Ростов-на-Дону|"
                r"Уфа|Краснодар|Пермь|Воронеж)"
            )
            # <CyrillicWord(s)>, <Number> — must end with typical street suffix OR be short
            m = re.search(
                r"([А-ЯЁ][а-яёА-ЯЁ\-]{3,25}(?:\s+[А-ЯЁ][а-яёА-ЯЁ\-]{2,15})?)"
                r",\s*(\d{1,3}[а-яА-Я]?(?:\s*[/\\]\s*\d+)?)"
                r"(?=\s|,|\.|\Z)",
                chunk,
            )
            if m:
                street_candidate = f"{m.group(1)}, {m.group(2)}"
                city_m = re.search(city_pat_loc, chunk, re.IGNORECASE)
                if city_m:
                    address = f"{city_m.group(0)}, {street_candidate}"
                else:
                    address = street_candidate
                address = re.sub(r"\s+", " ", address).strip()

    # 4. Fallback: look in HTML (in case address is inside a tag attribute or hidden)
    if not address:
        m = re.search(
            r"(?:ул\.|улица|просп?\.|проспект|пер\.|переулок)[\s\S]{3,60}?\d+",
            html,
        )
        if m:
            address = re.sub(r"<[^>]+>", "", m.group(0))
            address = re.sub(r"\s+", " ", address).strip()

    # --- Hours ---
    hours = ""
    # Patterns for time ranges
    time_range_pat = r"\d{1,2}[:.]\d{2}\s*[-–—]\s*\d{1,2}[:.]\d{2}"
    day_prefix_pat = (
        r"(?:ежедневно|пн[-–]вс|пн[-–]пт|пн[-–]чт|пн[-–]сб|"
        r"понедельник|вторник|среда|четверг|пятница|суббота|воскресенье|"
        r"пн|вт|ср|чт|пт|сб|вс)"
    )

    # 1. Try JSON-LD openingHours
    for ld_block in parser.ld_json_blocks:
        try:
            ld = _json.loads(ld_block)
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                if isinstance(item, dict):
                    oh = item.get("openingHours") or item.get("openingHoursSpecification")
                    if oh:
                        if isinstance(oh, list):
                            hours = "; ".join(str(x) for x in oh[:3])
                        else:
                            hours = str(oh)
                        break
        except Exception:
            pass
        if hours:
            break

    # 2. Look for day prefix + time range in plain text
    if not hours:
        m = re.search(
            rf"({day_prefix_pat})[^<\n]{{0,30}}({time_range_pat})",
            text_plain,
            re.IGNORECASE,
        )
        if m:
            # Grab from day-prefix start through end of time range only
            hours_raw = text_plain[m.start(): m.end()].strip()
            # Truncate after the time range (remove any trailing non-hours text)
            hours_raw = re.split(r"[\n\r\t]", hours_raw)[0].strip()
            # Cut at first non-hours character after time pattern (letters/JS)
            hours_raw = re.sub(r"\s+[a-zA-Z_\(\{][^\s]*.*$", "", hours_raw).strip()
            hours = re.sub(r"\s+", " ", hours_raw)[:80]

    # 3. Look for near working-hours keywords + time range
    if not hours:
        for label_pat in [
            r"(?:работаем|часы\s+работы|режим\s+работы|открыты|время\s+работы)[^\n<]{0,5}[:\s]*",
            r"(?:график\s+работы)[^\n<]{0,5}[:\s]*",
        ]:
            m = re.search(
                label_pat + rf"([^\n<]{{3,80}}?{time_range_pat}[^\n<]{{0,30}})",
                text_plain,
                re.IGNORECASE,
            )
            if m:
                hours = re.sub(r"\s+", " ", m.group(1)).strip()
                break

    # 4. Fallback: just a time range with optional day prefix nearby
    if not hours:
        m = re.search(time_range_pat, text_plain)
        if m:
            start = max(0, m.start() - 40)
            prefix_chunk = text_plain[start: m.end() + 5].strip()
            day_m = re.search(day_prefix_pat, prefix_chunk, re.IGNORECASE)
            if day_m:
                hours = re.sub(r"\s+", " ", prefix_chunk).strip()[:80]
            else:
                hours = re.sub(r"\s+", " ", m.group(0)).strip()

    # 5. Bare "ежедневно" if nothing else (but still try to append time from nearby)
    if not hours:
        m = re.search(r"ежедневно", text_plain, re.IGNORECASE)
        if m:
            nearby = text_plain[m.start(): m.start() + 60]
            t = re.search(time_range_pat, nearby)
            if t:
                hours = re.sub(r"\s+", " ", text_plain[m.start(): m.start() + t.end()]).strip()
            else:
                hours = "Ежедневно"

    hours = re.sub(r"\s+", " ", hours).strip()

    # --- venue_format ---
    # Infer from content; never return literal "lounge"
    venue_format = ""
    content_lower = (title + " " + description + " " + text_plain[:2000]).lower()
    if "кальян" in content_lower:
        venue_format = "Кальян-лаунж"
    elif "лаунж" in content_lower or "lounge" in content_lower:
        venue_format = "Лаунж"
    elif "бар" in content_lower:
        venue_format = "Бар"
    elif "ресторан" in content_lower:
        venue_format = "Ресторан"
    elif "кафе" in content_lower:
        venue_format = "Кафе"

    # --- tagline vs summary ---
    summary = description  # long description (og:description / meta)

    # Build a distinct tagline
    tagline = ""
    # Option 1: if og_title contains " | " or " — " or " - " use the part after separator
    for sep in (" | ", " — ", " - ", " – "):
        if sep in title:
            parts = title.split(sep, 1)
            candidate = parts[1].strip() if len(parts[0]) >= len(parts[1]) else parts[0].strip()
            if candidate and candidate != summary and len(candidate) <= 80:
                tagline = candidate
                break

    # Option 2: build "Кальян-лаунж · <street>" if we have address
    if not tagline or tagline == summary:
        vf = venue_format or "Лаунж"
        street_m = re.search(
            r"(?:ул\.|улица|просп?\.|проспект|пер\.|переулок)\s*[А-Яа-яЁё][А-Яа-яЁё\- ]{1,30}",
            address,
            re.IGNORECASE,
        )
        if street_m:
            tagline = f"{vf} · {street_m.group(0).strip()}"
        elif address:
            short_addr = address[:40].rsplit(" ", 1)[0] if len(address) > 40 else address
            tagline = f"{vf} · {short_addr}"

    # Option 3: truncate summary at word boundary (max 60 chars)
    if not tagline or tagline == summary:
        if summary:
            if len(summary) > 60:
                trunc = summary[:60].rsplit(" ", 1)[0]
                tagline = trunc + "…" if trunc != summary else summary[:57] + "…"
            else:
                # Make it shorter so it differs from full summary
                tagline = summary[:40].rsplit(" ", 1)[0] + "…" if len(summary) > 40 else ""

    # Ensure tagline != summary
    if tagline == summary:
        tagline = title[:60] if title != summary else ""

    # --- Strip tracking params from URLs ---
    def _clean_url(u: str) -> str:
        if not u:
            return u
        try:
            parts = _uparse.urlparse(u)
            qs = _uparse.parse_qs(parts.query, keep_blank_values=True)
            clean_qs = {
                k: v for k, v in qs.items()
                if not k.startswith(("utm_", "ysclid", "yclid", "_openstat", "from", "fbclid"))
            }
            new_query = _uparse.urlencode(clean_qs, doseq=True)
            return _uparse.urlunparse(parts._replace(query=new_query))
        except Exception:
            return u

    # --- Images ---
    parsed_base = _uparse.urlparse(final_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    def absolutize(src: str) -> str:
        if src.startswith("http"):
            return src
        if src.startswith("//"):
            return "https:" + src
        return _uparse.urljoin(base_origin, src)

    cover_url_remote = _clean_url(absolutize(parser.og_image)) if parser.og_image else ""

    extra_images = []
    for src in parser.images:
        abs_src = absolutize(src)
        ext_lower = abs_src.lower().split("?")[0]
        if not any(ext_lower.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
            continue
        if "tildacdn" in abs_src or "thb.tildacdn" in abs_src or parsed_base.netloc in abs_src:
            clean = _clean_url(abs_src)
            if clean != cover_url_remote and clean not in extra_images:
                extra_images.append(clean)
        if len(extra_images) >= 8:
            break

    avatar_url_remote = cover_url_remote

    brand_id_suggestion = _domain_slug(url)

    return {
        "title": title,
        "description": description,
        "tagline": tagline,
        "summary": summary,
        "phone": phone,
        "address": address,
        "hours": hours,
        "venue_format": venue_format,
        "cover_url_remote": cover_url_remote,
        "avatar_url_remote": avatar_url_remote,
        "extra_image_urls": extra_images[:8],
        "brand_id_suggestion": brand_id_suggestion,
        "source_url": url,
    }


@app.get("/admin-web/lounges/new", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_lounge_new_get(
    request: Request,
    db: Session = Depends(get_db),
    flash_err: str = Query(default=None),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)
    ctx = {
        "active_nav": "lounges",
        "admin_email": admin.email,
        "flash_err": flash_err,
        "parsed": None,
        "form": {},
    }
    return templates.TemplateResponse(request, "lounge_new.html", ctx)


@app.post("/admin-web/lounges/parse", response_class=HTMLResponse, tags=["admin-web"])
async def admin_web_lounge_parse(
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    form = await request.form()
    url = (form.get("url") or "").strip()
    flash_err = None
    parsed_data = None

    if url:
        try:
            parsed_data = _parse_lounge_url_internal(url)
        except Exception as e:
            flash_err = f"Не удалось спарсить сайт: {e}"

    ctx = {
        "active_nav": "lounges",
        "admin_email": admin.email,
        "flash_err": flash_err,
        "parsed": parsed_data,
        "form": parsed_data or {},
        "parse_url": url,
    }
    return templates.TemplateResponse(request, "lounge_new.html", ctx)


@app.post("/admin-web/lounges/new", tags=["admin-web"])
async def admin_web_lounge_new_post(
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    form = await request.form()

    brand_id = _slugify((form.get("brand_id") or "").strip())
    if not brand_id:
        return RedirectResponse(
            url="/admin-web/lounges/new?flash_err=brand_id+is+required",
            status_code=302,
        )

    title = (form.get("title") or brand_id).strip()
    city = (form.get("city") or "").strip()
    address = (form.get("address") or "").strip()
    phone = (form.get("phone") or "").strip()
    hours = (form.get("hours") or "").strip()
    category = (form.get("category") or "lounge").strip()
    tier = (form.get("tier") or "start").strip()
    tagline = (form.get("tagline") or "").strip()
    summary = (form.get("summary") or "").strip()
    source_url = (form.get("source_url") or "").strip()

    # --- Download images ---
    cover_url_remote = (form.get("cover_url_remote") or "").strip()
    avatar_url_remote = (form.get("avatar_url_remote") or "").strip()
    extra_images_raw = (form.get("extra_image_urls") or "").strip()
    extra_image_urls = [u.strip() for u in extra_images_raw.splitlines() if u.strip()]

    # /app/static is the container path (host volume: /opt/hooka-backend/static)
    static_dir = f"/app/static/lounges/{brand_id}"
    static_url_base = f"http://188.253.19.166:8000/static/lounges/{brand_id}"
    os.makedirs(static_dir, exist_ok=True)

    cover_url_local = ""
    avatar_url_local = ""
    photo_urls_local = []

    idx = 0
    for remote_url in ([cover_url_remote] + extra_image_urls):
        if not remote_url:
            continue
        ext = "jpg"
        for candidate_ext in ("webp", "png", "jpg", "jpeg"):
            if f".{candidate_ext}" in remote_url.lower().split("?")[0]:
                ext = candidate_ext
                break
        dest = os.path.join(static_dir, f"{idx}.{ext}")
        ok = _download_image(remote_url, dest)
        if ok:
            local_url = f"{static_url_base}/{idx}.{ext}"
            if idx == 0:
                cover_url_local = local_url
                import shutil as _shutil
                avatar_dest = os.path.join(static_dir, f"avatar.{ext}")
                _shutil.copy2(dest, avatar_dest)
                avatar_url_local = f"{static_url_base}/avatar.{ext}"
            # ALL downloaded images go into the gallery (cover included at position 0)
            photo_urls_local.append(local_url)
            idx += 1

    if avatar_url_remote and avatar_url_remote != cover_url_remote:
        dest = os.path.join(static_dir, "avatar.jpg")
        ok = _download_image(avatar_url_remote, dest)
        if ok:
            avatar_url_local = f"{static_url_base}/avatar.jpg"

    # --- Build profile_json matching myata_platinum contract ---
    venue_address_full = f"{city}, {address}".strip(", ") if city else address
    phone_clean = re.sub(r"[\s\-\(\)]", "", phone)
    phone_tel = f"tel://{phone_clean}" if phone_clean else ""

    profile_json_dict = {
        "brand_id": brand_id,
        "title": title,
        "category": category,
        "accent_hex": "A8F55F",
        "secondary_hex": "15220F",
        "badge": "Lounge",
        "tagline": tagline or title,
        "summary": summary or title,
        "signature": "",
        "heritage": "",
        "best_for": "",
        "lines": [],
        "highlights": [],
        "aliases": [brand_id, title],
        "hero_symbol": "leaf.fill",
        "logo_image_url": None,
        "hero_image_url": cover_url_local or None,
        "avatar_url": avatar_url_local or None,
        "cover_url": cover_url_local or None,
        "official_authors": [brand_id, title],
        "venue_address": venue_address_full,
        "nearest_metro": "",
        "venue_latitude": None,
        "venue_longitude": None,
        "venue_hours": hours,
        "venue_price": "",
        "venue_format": category,
        "venue_phone": phone,
        "venue_booking_url": source_url,
        "venue_menu_url": source_url,
        "venue_loyalty_title": "",
        "venue_loyalty_summary": "",
        "articles": [],
        "menu_highlights": [],
        "service_cards": (
            [
                {
                    "id": f"{brand_id}_open",
                    "title": "Открыть сайт",
                    "subtitle": source_url,
                    "icon_name": "safari.fill",
                    "destination_url": source_url,
                },
                {
                    "id": f"{brand_id}_call",
                    "title": "Позвонить",
                    "subtitle": phone,
                    "icon_name": "phone.fill",
                    "destination_url": phone_tel,
                },
            ]
            if source_url
            else []
        ),
    }

    profile_json_str = json.dumps(profile_json_dict, ensure_ascii=False)
    photo_urls_json = json.dumps(photo_urls_local, ensure_ascii=False)

    # --- UPSERT lounge_catalog ---
    # Note: use CAST(:pj AS jsonb) — SQLAlchemy sa_text() treats :: as Python
    # slice syntax for named params, so the explicit CAST form is safer.
    db.execute(
        sa_text(
            """
            INSERT INTO lounge_catalog (brand_id, profile_json, is_active, updated_at)
            VALUES (:bid, CAST(:pj AS jsonb), true, now())
            ON CONFLICT (brand_id) DO UPDATE
                SET profile_json = EXCLUDED.profile_json,
                    is_active    = true,
                    updated_at   = now()
            """
        ),
        {"bid": brand_id, "pj": profile_json_str},
    )

    # --- UPSERT lounge_assets ---
    db.execute(
        sa_text(
            """
            INSERT INTO lounge_assets (brand_id, avatar_url, cover_url, photo_urls, info_json, updated_at)
            VALUES (:bid, :av, :cv, :pu, '{}', now())
            ON CONFLICT (brand_id) DO UPDATE
                SET avatar_url  = EXCLUDED.avatar_url,
                    cover_url   = EXCLUDED.cover_url,
                    photo_urls  = EXCLUDED.photo_urls,
                    updated_at  = now()
            """
        ),
        {
            "bid": brand_id,
            "av": avatar_url_local or None,
            "cv": cover_url_local or None,
            "pu": photo_urls_json,
        },
    )

    # --- Ensure LoungeAdminMeta row exists ---
    meta_row = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if meta_row is None:
        meta_row = LoungeAdminMeta(brand_id=brand_id, tier=tier, badges=[])
        db.add(meta_row)
    else:
        meta_row.tier = tier

    db.commit()

    # --- Ensure lounge owner account + credentials ---
    try:
        ensure_lounge_owner(brand_id, db, title=title)
    except Exception as _owner_exc:
        import logging as _lg
        _lg.getLogger(__name__).warning("ensure_lounge_owner failed for %s: %s", brand_id, _owner_exc)

    imgs_count = (1 if cover_url_local else 0) + len(photo_urls_local)
    flash_msg = (
        f"Лаунж {brand_id} создан. "
        f"Картинок скачано: {imgs_count}. "
        f"Видно в /catalog/lounges."
    )
    return RedirectResponse(
        url=f"/admin-web/lounges?flash_ok={urllib.parse.quote(flash_msg)}",
        status_code=302,
    )


# ---------------------------------------------------------------
# GET /admin-web/lounges/{brand_id}
# ---------------------------------------------------------------
@app.get("/admin-web/lounges/{brand_id}", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_lounge_detail(
    brand_id: str,
    request: Request,
    db: Session = Depends(get_db),
    flash_ok: str = Query(default=None),
    flash_err: str = Query(default=None),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    cutoff_30 = datetime.utcnow() - timedelta(days=30)

    meta_row = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    meta = {
        "tier": meta_row.tier if meta_row else "start",
        "badges": (meta_row.badges if isinstance(meta_row.badges, list) else []) if meta_row else [],
        "notes": meta_row.notes if meta_row else None,
    }

    visits_30d = (
        db.query(func.count(LoungeVisit.id))
        .filter(LoungeVisit.brand_id == brand_id, LoungeVisit.created_at >= cutoff_30)
        .scalar() or 0
    )
    visits_total = (
        db.query(func.count(LoungeVisit.id))
        .filter(LoungeVisit.brand_id == brand_id)
        .scalar() or 0
    )
    guests_count = (
        db.query(func.count(LoungeGuestLoyalty.id))
        .filter(LoungeGuestLoyalty.brand_id == brand_id)
        .scalar() or 0
    )
    bonus_outstanding = (
        db.query(func.coalesce(func.sum(LoungeGuestLoyalty.bonus_balance), 0))
        .filter(LoungeGuestLoyalty.brand_id == brand_id)
        .scalar() or 0
    )
    promos_active = (
        db.query(func.count(LoungePromo.id))
        .filter(LoungePromo.brand_id == brand_id, LoungePromo.active == True)
        .scalar() or 0
    )

    sub_history_rows = (
        db.query(LoungeBillingSubscription)
        .filter(LoungeBillingSubscription.brand_id == brand_id)
        .order_by(LoungeBillingSubscription.expires_at.desc())
        .limit(20)
        .all()
    )
    sub_history = [
        {
            "id": s.id,
            "tier": s.tier,
            "status": s.status,
            "payment_method": s.payment_method,
            "started_at": _fmt_dt(s.started_at),
            "expires_at": _fmt_dt(s.expires_at),
        }
        for s in sub_history_rows
    ]

    owner_creds_row = db.query(LoungeOwnerCredentials).filter(
        LoungeOwnerCredentials.brand_id == brand_id
    ).first()
    owner_creds = None
    if owner_creds_row:
        owner_creds = {
            "email": owner_creds_row.email,
            "username": owner_creds_row.username,
            "password": owner_creds_row.password_plain,
            "user_id": owner_creds_row.user_id,
        }

    ctx = {
        "active_nav": "lounges",
        "admin_email": admin.email,
        "brand_id": brand_id,
        "meta": meta,
        "stats": {
            "visits_30d": visits_30d,
            "visits_total": visits_total,
            "guests_count": guests_count,
            "bonus_outstanding": int(bonus_outstanding),
            "promos_active": promos_active,
        },
        "sub_history": sub_history,
        "owner_creds": owner_creds,
        "flash_ok": flash_ok,
        "flash_err": flash_err,
    }
    return templates.TemplateResponse(request, "lounge_detail.html", ctx)


# ---------------------------------------------------------------
# POST /admin-web/lounges/{brand_id}/create-owner
# ---------------------------------------------------------------
@app.post("/admin-web/lounges/{brand_id}/create-owner", tags=["admin-web"])
async def admin_web_create_owner(
    brand_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    try:
        creds = ensure_lounge_owner(brand_id, db)
        flash_msg = f"Доступ создан: {creds['email']} / {creds['password']}"
        return RedirectResponse(
            url=f"/admin-web/lounges/{brand_id}?flash_ok={urllib.parse.quote(flash_msg)}",
            status_code=302,
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"/admin-web/lounges/{brand_id}?flash_err={urllib.parse.quote(str(exc))}",
            status_code=302,
        )


# ---------------------------------------------------------------
# POST /admin-web/lounges/{brand_id}/reset-owner-password
# ---------------------------------------------------------------
@app.post("/admin-web/lounges/{brand_id}/reset-owner-password", tags=["admin-web"])
async def admin_web_reset_owner_password(
    brand_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    creds_row = db.query(LoungeOwnerCredentials).filter(
        LoungeOwnerCredentials.brand_id == brand_id
    ).first()
    if not creds_row:
        return RedirectResponse(
            url=f"/admin-web/lounges/{brand_id}?flash_err=No+owner+account+found",
            status_code=302,
        )

    new_password = _gen_owner_password()
    # Update the User record
    if creds_row.user_id:
        user_row = db.query(User).filter(User.id == creds_row.user_id).first()
        if user_row:
            user_row.password_hash = hash_password(new_password)

    creds_row.password_plain = new_password
    db.commit()

    flash_msg = f"Пароль сброшен. Новый: {new_password}"
    return RedirectResponse(
        url=f"/admin-web/lounges/{brand_id}?flash_ok={urllib.parse.quote(flash_msg)}",
        status_code=302,
    )


# ---------------------------------------------------------------
# POST /admin-web/lounges/{brand_id}/grant-trial
# ---------------------------------------------------------------
@app.post("/admin-web/lounges/{brand_id}/grant-trial", tags=["admin-web"])
async def admin_web_grant_trial(
    brand_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    form = await request.form()
    tier = form.get("tier", "pro").strip()
    try:
        days = int(form.get("days", 30))
    except (ValueError, TypeError):
        days = 30
    payment_method = form.get("payment_method", "trial").strip()

    valid_tiers = {"start", "lite", "pro", "network", "partner"}
    if tier not in valid_tiers:
        tier = "pro"
    if days <= 0:
        days = 30

    now = datetime.utcnow()
    existing = (
        db.query(LoungeBillingSubscription)
        .filter(
            LoungeBillingSubscription.brand_id == brand_id,
            LoungeBillingSubscription.expires_at > now,
            LoungeBillingSubscription.status.in_(["active", "trialing"]),
        )
        .order_by(LoungeBillingSubscription.expires_at.desc())
        .first()
    )
    start_from = existing.expires_at if existing else now
    new_expires = start_from + timedelta(days=days)
    status = "trialing" if payment_method == "trial" else "active"

    sub = LoungeBillingSubscription(
        brand_id=brand_id,
        tier=tier,
        status=status,
        started_at=now,
        expires_at=new_expires,
        payment_method=payment_method,
    )
    db.add(sub)

    # Also sync tier in LoungeAdminMeta
    meta_row = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if meta_row is None:
        meta_row = LoungeAdminMeta(brand_id=brand_id, tier=tier, badges=[])
        db.add(meta_row)
    else:
        meta_row.tier = tier
    db.commit()

    return RedirectResponse(
        url=f"/admin-web/lounges/{brand_id}?flash_ok=Subscription+granted+{tier}+{days}d",
        status_code=302,
    )


# ---------------------------------------------------------------
# POST /admin-web/lounges/{brand_id}/patch
# ---------------------------------------------------------------
@app.post("/admin-web/lounges/{brand_id}/patch", tags=["admin-web"])
async def admin_web_patch_lounge(
    brand_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    form = await request.form()
    tier = form.get("tier", "").strip()
    notes = form.get("notes", "").strip() or None

    valid_tiers = {"start", "lite", "pro", "network", "partner"}
    if tier not in valid_tiers:
        tier = None

    meta_row = db.query(LoungeAdminMeta).filter(LoungeAdminMeta.brand_id == brand_id).first()
    if meta_row is None:
        meta_row = LoungeAdminMeta(brand_id=brand_id, tier=tier or "start", badges=[])
        db.add(meta_row)
    else:
        if tier:
            meta_row.tier = tier
        meta_row.notes = notes
    db.commit()

    return RedirectResponse(
        url=f"/admin-web/lounges/{brand_id}?flash_ok=Saved",
        status_code=302,
    )


# ---------------------------------------------------------------
# GET /admin-web/subscriptions
# ---------------------------------------------------------------
@app.get("/admin-web/subscriptions", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_subscriptions(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    status: str = Query(default=None),
    brand_id: str = Query(default=None),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    per_page = 50
    base_q = db.query(LoungeBillingSubscription)
    if status:
        base_q = base_q.filter(LoungeBillingSubscription.status == status)
    if brand_id:
        base_q = base_q.filter(LoungeBillingSubscription.brand_id.ilike(f"%{brand_id}%"))

    total = base_q.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    rows = (
        base_q.order_by(LoungeBillingSubscription.expires_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    subs_out = [
        {
            "id": s.id,
            "brand_id": s.brand_id,
            "tier": s.tier,
            "status": s.status,
            "payment_method": s.payment_method,
            "created_at": _fmt_dt(s.created_at),
            "started_at": _fmt_dt(s.started_at),
            "expires_at": _fmt_dt(s.expires_at),
        }
        for s in rows
    ]

    ctx = {
        "active_nav": "subscriptions",
        "admin_email": admin.email,
        "subs": subs_out,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "status_filter": status,
        "brand_id_filter": brand_id,
    }
    return templates.TemplateResponse(request, "subscriptions.html", ctx)


# GET /admin-web/featured
# ---------------------------------------------------------------
@app.get("/admin-web/featured", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_featured(
    request: Request,
    db: Session = Depends(get_db),
    status: Optional[str] = Query(default="active"),
    flash_ok: Optional[str] = Query(default=None),
    flash_err: Optional[str] = Query(default=None),
    flash_create_err: Optional[str] = Query(default=None),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    now = datetime.utcnow()
    q = db.query(FeaturedSlot)
    if status:
        q = q.filter(FeaturedSlot.status == status)
    rows = q.order_by(FeaturedSlot.expires_at.desc()).all()

    slots_out = []
    for r in rows:
        remaining = max(0, (r.expires_at - now).days)
        slots_out.append({
            "id": r.id,
            "brand_id": r.brand_id,
            "slot_type": r.slot_type,
            "city": r.city,
            "expires_at": _fmt_dt(r.expires_at),
            "price_paid": r.price_paid or 0,
            "status": r.status,
            "payment_method": r.payment_method,
            "remaining_days": remaining,
        })

    # Collect known brand IDs for autocomplete
    brand_ids: set = set()
    for row in db.query(LoungeAdminMeta.brand_id).all():
        brand_ids.add(row.brand_id)
    for row in db.query(FeaturedSlot.brand_id).distinct().all():
        brand_ids.add(row.brand_id)

    ctx = {
        "active_nav": "featured",
        "admin_email": admin.email,
        "slots": slots_out,
        "total": len(slots_out),
        "status_filter": status,
        "known_brands": sorted(brand_ids),
        "flash_ok": flash_ok,
        "flash_err": flash_err,
        "flash_create_err": flash_create_err,
    }
    return templates.TemplateResponse(request, "featured.html", ctx)


# POST /admin-web/featured/create
# ---------------------------------------------------------------
@app.post("/admin-web/featured/create", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_featured_create(
    request: Request,
    db: Session = Depends(get_db),
    brand_id: str = Form(...),
    slot_type: str = Form(...),
    city: str = Form("general"),
    days: int = Form(7),
    price_paid: int = Form(0),
    payment_method: str = Form("manual"),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    now = datetime.utcnow()
    starts_at = now
    expires_at = now + timedelta(days=days)

    # Tier check
    tier = get_active_tier(db, brand_id)
    from app.services.subscriptions import _tier_rank
    if _tier_rank(tier) < _tier_rank("pro"):
        err = f"Лаунж '{brand_id}' имеет тариф '{tier}'. Требуется pro+"
        return RedirectResponse(
            url=f"/admin-web/featured?flash_create_err={err}",
            status_code=302,
        )

    # Hero conflict check
    if slot_type == "hero":
        conflict = db.query(FeaturedSlot).filter(
            FeaturedSlot.slot_type == "hero",
            FeaturedSlot.city == city,
            FeaturedSlot.status == "active",
            FeaturedSlot.expires_at > now,
        ).first()
        if conflict:
            err = f"Hero для '{city}' занят: {conflict.brand_id}"
            return RedirectResponse(
                url=f"/admin-web/featured?flash_create_err={err}",
                status_code=302,
            )

    slot = FeaturedSlot(
        brand_id=brand_id,
        slot_type=slot_type,
        city=city,
        starts_at=starts_at,
        expires_at=expires_at,
        price_paid=price_paid,
        status="active",
        payment_method=payment_method,
        created_by_admin=True,
        created_at=now,
    )
    db.add(slot)
    db.commit()

    return RedirectResponse(
        url=f"/admin-web/featured?flash_ok=Слот+создан+для+{brand_id}",
        status_code=302,
    )


# POST /admin-web/featured/{slot_id}/cancel
# ---------------------------------------------------------------
@app.post("/admin-web/featured/{slot_id}/cancel", response_class=HTMLResponse, tags=["admin-web"])
def admin_web_featured_cancel(
    slot_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    admin = _admin_web_user(request, db)
    if not admin:
        return RedirectResponse(url="/admin-web/login", status_code=302)

    slot = db.query(FeaturedSlot).filter(FeaturedSlot.id == slot_id).first()
    if not slot:
        return RedirectResponse(
            url="/admin-web/featured?flash_err=Слот+не+найден",
            status_code=302,
        )
    slot.status = "cancelled"
    db.commit()
    return RedirectResponse(
        url=f"/admin-web/featured?flash_ok=Слот+{slot_id}+отменён",
        status_code=302,
    )


# -------------------------------------------------------------------
# CATALOG — Server-driven lounge catalog (2026-05-28)
# No auth required. iOS app fetches this to show new lounges without rebuild.
# -------------------------------------------------------------------

@app.get("/catalog/lounges", tags=["catalog"])
def catalog_lounges(db: Session = Depends(get_db)):
    """Return all active lounge profiles from the server-driven catalog."""
    rows = db.execute(
        sa_text("SELECT profile_json FROM lounge_catalog WHERE is_active = true ORDER BY updated_at DESC")
    ).fetchall()
    return {"lounges": [row[0] for row in rows]}

