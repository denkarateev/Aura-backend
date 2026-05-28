from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.config import BOWL_HEAT_DURATION_SECONDS


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    ton_address = Column(String, nullable=True)
    username = Column(String, unique=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(Text)
    banned_at = Column(DateTime)
    # Premium subscription — nullable. premium_until ≥ now() means active.
    premium_until = Column(DateTime, nullable=True)
    premium_plan = Column(String, nullable=True)  # premium_monthly | premium_yearly
    premium_provider = Column(String, nullable=True)  # yookassa | storekit
    # Account type — 'user' (default), 'master', 'lounge_owner'
    account_type = Column(String(20), default="user", nullable=False, server_default="user")
    # FK to master_profiles (set when account_type='master')
    master_profile_id = Column(String, nullable=True)
    # Optional profile fields (mirror ALTER TABLE migrations on startup).
    display_name = Column(Text, nullable=True)
    phone = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    city = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    # Soft-delete flag. App Store 5.1.1(v) compliance — DELETE /users/me sets
    # this to True and scrubs PII on the row. All auth checks reject deleted
    # accounts at get_current_user.
    is_deleted = Column(Boolean, default=False, nullable=False, server_default="false")
    # Legal consent — timestamp when user accepted Terms of Use & Privacy Policy.
    # Required at signup (152-FZ / App Store legal compliance).
    accepted_terms_at = Column(DateTime(timezone=True), nullable=True)
    # CRM privacy — allow lounge owners to see guest's tobacco flavor preferences.
    # Default TRUE for backward compat. Added via startup ALTER TABLE.
    share_flavors = Column(Boolean, default=True, nullable=False, server_default="true")

    mixes = relationship("Mix", back_populates="author")
    favorites = relationship("Favorite", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    following_links = relationship(
        "UserFollow",
        foreign_keys="UserFollow.follower_id",
        back_populates="follower",
        cascade="all, delete-orphan"
    )
    follower_links = relationship(
        "UserFollow",
        foreign_keys="UserFollow.following_id",
        back_populates="following",
        cascade="all, delete-orphan"
    )
    progress = relationship("UserProgress", back_populates="user", uselist=False)
    activities = relationship(
        "UserActivity",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    bowl_heat_runs = relationship(
        "BowlHeatRun",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    lounge_loyalty_states = relationship(
        "LoungeGuestLoyalty",
        foreign_keys="LoungeGuestLoyalty.user_id",
        cascade="all, delete-orphan"
    )
    lounge_personalizations = relationship(
        "LoungeGuestPersonalization",
        foreign_keys="LoungeGuestPersonalization.user_id",
        cascade="all, delete-orphan"
    )


class Mix(Base):
    __tablename__ = "mixes"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"))

    name = Column(String, nullable=False)
    mood = Column(String)
    intensity = Column(Float)
    description = Column(Text)
    bowl_type = Column(String)
    packing_style = Column(String)
    bowl_image_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # MARK: Mix Wizard fields (S2026-04-29) — added via startup ALTER TABLE
    # status: 'public' | 'subscribers' | 'draft'
    status = Column(
        String(20),
        nullable=False,
        default="public",
        server_default="public",
    )
    # Soft FK to brands.id where category='lounge' (no DB constraint, brands
    # table is owned by iOS-side seed data — backend just stores the id).
    lounge_id = Column(String, nullable=True)
    # JSON-encoded list of strings. Stored as TEXT to keep parity with
    # LoungeAssets.photo_urls / info_json. JSON parse/dump in API layer.
    tags = Column(Text, nullable=True, default="[]", server_default="[]")

    author = relationship("User", back_populates="mixes")
    ingredients = relationship(
        "MixIngredient",
        cascade="all, delete-orphan"
    )
    comments = relationship(
        "Comment",
        cascade="all, delete-orphan"
    )
    favorited_by = relationship(
        "Favorite",
        back_populates="mix"
    )


class MixIngredient(Base):
    __tablename__ = "mix_ingredients"

    id = Column(Integer, primary_key=True)
    mix_id = Column(Integer, ForeignKey("mixes.id"))
    brand = Column(String)
    flavor = Column(String)
    percentage = Column(Integer)


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mix_id = Column(Integer, ForeignKey("mixes.id"))
    # Когда лайк поставили — нужно для leaderboard «топ забивок недели»
    # (считаем лайки полученные в период). Бэкфилл NULL→utcnow при
    # первом деплое: scripts/add_favorites_created_at.sql.
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (UniqueConstraint("user_id", "mix_id"),)

    user = relationship("User", back_populates="favorites")
    mix = relationship("Mix", back_populates="favorited_by")


class UserFollow(Base):
    __tablename__ = "user_follows"

    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("follower_id", "following_id"),)

    follower = relationship(
        "User",
        foreign_keys=[follower_id],
        back_populates="following_links"
    )
    following = relationship(
        "User",
        foreign_keys=[following_id],
        back_populates="follower_links"
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    mix_id = Column(Integer, ForeignKey("mixes.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="comments")
    mix = relationship("Mix", back_populates="comments")


class MonthlyVote(Base):
    __tablename__ = "monthly_votes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mix_id = Column(Integer, ForeignKey("mixes.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    points = Column(Integer, default=0, nullable=False)
    rating = Column(Integer, default=0, nullable=False)
    streak_days = Column(Integer, default=0, nullable=False)
    last_active_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="progress")


class UserActivity(Base):
    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    points_delta = Column(Integer, default=0, nullable=False)
    rating_delta = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="activities")


class BowlHeatRun(Base):
    __tablename__ = "bowl_heat_runs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, default=0, nullable=False)
    sweet_spot_seconds = Column(Float, default=0, nullable=False)
    overheat_seconds = Column(Float, default=0, nullable=False)
    taps_count = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Float, default=BOWL_HEAT_DURATION_SECONDS, nullable=False)
    reward_points = Column(Integer, default=0, nullable=False)
    reward_rating = Column(Integer, default=0, nullable=False)
    tier_title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="bowl_heat_runs")


class LoungeProgram(Base):
    __tablename__ = "lounge_programs"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    base_discount_percent = Column(Integer, default=5, nullable=False)
    welcome_offer_title = Column(String, nullable=False)
    welcome_offer_body = Column(Text, nullable=False)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LoungeGuestLoyalty(Base):
    __tablename__ = "lounge_guest_loyalties"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    visit_count = Column(Integer, default=0, nullable=False)
    last_visit_at = Column(DateTime)
    # Added in prod via manual ALTER for "≤3 visits/day per guest" rule.
    today_visit_count = Column(Integer, default=0)
    today_date = Column(Date)
    # Per-lounge bonus balance (separate from общие угольки in UserProgress.points).
    # Added 2026-05-26: ALTER TABLE lounge_guest_loyalty ADD COLUMN IF NOT EXISTS bonus_balance.
    bonus_balance = Column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (UniqueConstraint("brand_id", "user_id"),)


class LoungeGuestPersonalization(Base):
    __tablename__ = "lounge_guest_personalizations"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    display_name = Column(String)
    favorite_order = Column(Text)
    average_check = Column(Integer)
    visit_count = Column(Integer, default=1, nullable=False)
    personal_tier_title = Column(String)
    personal_discount_percent = Column(Integer)
    personal_offer_title = Column(String)
    personal_offer_body = Column(Text)
    note = Column(Text)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("brand_id", "user_id"),)


class LoungeBusinessEvent(Base):
    __tablename__ = "lounge_business_events"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"))
    guest_user_id = Column(Integer, ForeignKey("users.id"))
    master_id = Column(String, ForeignKey("masters.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Event(Base):
    """Public lounge event/promo shown in Events and lounge profiles."""
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    subtitle = Column(Text, nullable=True)
    kind = Column(String(40), nullable=False, default="promo", server_default="promo")
    mood = Column(String(40), nullable=False, default="warm", server_default="warm")
    lounge_id = Column(String, nullable=True, index=True)
    venue_title = Column(String, nullable=True)
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=True)
    recurrence = Column(Text, nullable=True)
    cover_image_url = Column(Text, nullable=True)
    price_text = Column(String, nullable=True)
    booking_url = Column(Text, nullable=True)
    # Прод хранит как PostgreSQL ARRAY(Text). Передаём питон-list,
    # SQLAlchemy сам соберёт в `{a,b}` синтаксис. JSON-обёртка убрана
    # (раньше пытались писать '[]' в text[] и получали InvalidTextRepresentation).
    tags = Column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rsvps = relationship(
        "EventRSVP",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class EventRSVP(Base):
    """Current user's RSVP state for an event.

    Прод-схема: composite PK (event_id, user_id) — без отдельного id.
    Колонка `going_at` (timestamptz) хранит timestamp подтверждения.
    """
    __tablename__ = "event_rsvps"

    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    going_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    going = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="rsvps")


class Duel(Base):
    __tablename__ = "duels"
    id = Column(String, primary_key=True)
    brand_id = Column(String, nullable=False)
    guest_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    host_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="waiting")  # waiting/active/finished/expired
    guest_score = Column(Integer, default=0)
    host_score = Column(Integer, default=0)
    winner_id = Column(Integer, nullable=True)
    base_discount = Column(Integer, default=5)
    duel_discount = Column(Integer, default=10)
    join_code = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


# MARK: - Pre-paid lounge bundle subscriptions

class LoungeBundle(Base):
    """
    A pre-paid pack giving the owner a per-visit discount at a set of
    partner lounges. Each check-in at a covered lounge creates a
    LoungeBundleVisit and queues a LoungeLedgerEntry that settles to
    the lounge on the next monthly payout.
    """
    __tablename__ = "lounge_bundles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tier = Column(String, nullable=False)  # five | ten | cityPass | group
    lounge_ids = Column(Text, nullable=False, default="")  # comma-separated brand ids; empty for cityPass
    discount_percent = Column(Integer, nullable=False, default=10)
    max_visits = Column(Integer, nullable=False)  # tier.maxLounges; 0 means unlimited (cityPass)
    compensation_per_visit_rub = Column(Integer, nullable=False)
    price_rub = Column(Integer, nullable=False)
    purchase_provider = Column(String, nullable=False)  # yookassa | apple_storekit
    purchase_receipt_id = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="active")  # active | expired | refunded

    visits = relationship(
        "LoungeBundleVisit",
        back_populates="bundle",
        cascade="all, delete-orphan",
        order_by="LoungeBundleVisit.visited_at",
    )


class LoungeBundleVisit(Base):
    """
    One redemption of a bundle at a specific lounge. Created by the
    /lounges/{id}/checkin endpoint when the guest has an active bundle
    covering that lounge. Backed by a ledger entry for payout.
    """
    __tablename__ = "lounge_bundle_visits"

    id = Column(Integer, primary_key=True)
    bundle_id = Column(Integer, ForeignKey("lounge_bundles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    brand_id = Column(String, nullable=False, index=True)
    master_id = Column(String, ForeignKey("masters.id"), nullable=True, index=True)
    compensation_rub = Column(Integer, nullable=False)
    visited_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    bundle = relationship("LoungeBundle", back_populates="visits")


class DeviceToken(Base):
    """APNs / FCM device token registered per user. One user can have
    multiple devices (phone + iPad), so (user_id, token) is unique.
    Old tokens are expected to be replaced when the OS rotates them."""
    __tablename__ = "device_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String, nullable=False, unique=True)
    platform = Column(String, nullable=False, default="ios")  # ios | android
    app_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LoungeAssets(Base):
    """
    Static media assets and structured info for a lounge brand.
    Stored on backend to avoid parsing/scraping on iOS client side.

    avatar_url  — square logo / avatar (400×400), shown in lists and cards
    cover_url   — hero cover image (1200×675, 16:9), shown on brand profile header
    photo_urls  — JSON array of gallery photo URLs (up to 10)
    info_json   — JSON object: cuisine, atmosphere, signature_mix, vibe, address, etc.
    """
    __tablename__ = "lounge_assets"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String, unique=True, nullable=False, index=True)
    avatar_url = Column(Text, nullable=True)
    cover_url = Column(Text, nullable=True)
    photo_urls = Column(Text, nullable=True, default="[]")  # JSON array string
    info_json = Column(Text, nullable=True, default="{}")   # JSON object string
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ManagerTelegramLink(Base):
    """
    Links a brand manager's Hooka3 account to their Telegram chat.

    Flow:
      1. Manager calls POST /me/telegram/link-code → gets 6-digit code (10 min TTL).
         A row is created with link_code set and verified_at=NULL.
      2. Manager opens @hooka3_busyness_bot, sends /start <CODE>.
         Bot finds row by link_code, fills telegram_chat_id + verified_at,
         clears link_code.
      3. Scheduler queries verified rows every 30 min, sends busyness poll
         to each chat with inline buttons per managed brand.
      4. Button callback writes to LoungeAssets.info_json["busyness"].
    """
    __tablename__ = "manager_telegram_links"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    telegram_chat_id = Column(BigInteger, nullable=True, unique=True, index=True)
    telegram_username = Column(String, nullable=True)
    link_code = Column(String, nullable=True, index=True)  # cleared after verification
    code_expires_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    last_poll_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LoungeLedgerEntry(Base):
    """
    Double-sided accounting ledger for bundle settlement.

    direction = "outflow" — Hooka3 pays the lounge (per bundle visit).
    direction = "inflow"  — Hooka3 receives from the user (bundle sale).

    On the monthly payout, all pending outflow entries for a given
    lounge are aggregated, the sum is transferred, and status flips
    to "settled".
    """
    __tablename__ = "lounge_ledger_entries"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String, nullable=True, index=True)  # null for inflow (sale)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    bundle_id = Column(Integer, ForeignKey("lounge_bundles.id"), nullable=True)
    bundle_visit_id = Column(Integer, ForeignKey("lounge_bundle_visits.id"), nullable=True)
    direction = Column(String, nullable=False)  # outflow | inflow
    amount_rub = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="pending", index=True)  # pending | settled
    description = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    settled_at = Column(DateTime, nullable=True)
    settlement_batch_id = Column(String, nullable=True, index=True)


# MARK: - Masters domain

class Master(Base):
    """
    Hookah master public profile.
    Main table: 'masters' (already in production from S192-S194).
    Extended with is_verified, reviews_count, user_id via startup ALTER TABLE.
    """
    __tablename__ = "masters"

    id = Column(String, primary_key=True)               # e.g. "master_alexey"
    handle = Column(String(40), unique=True, nullable=False)
    display_name = Column(String(120), nullable=False)
    avatar_url = Column(Text, nullable=True)
    current_lounge_id = Column(Text, nullable=True)
    bio = Column(Text, nullable=True)
    accent_color_hex = Column(Text, nullable=True)
    mixes_count = Column(Integer, default=0, nullable=False)
    followers_count = Column(Integer, default=0, nullable=False)
    rating = Column(Float, default=0.0, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Extended columns added via startup ALTER TABLE
    is_verified = Column(Boolean, default=False, nullable=False, server_default="false")
    reviews_count = Column(Integer, default=0, nullable=False, server_default="0")
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)

    work_history = relationship(
        "MasterWorkHistory",
        back_populates="master",
        cascade="all, delete-orphan",
        order_by="MasterWorkHistory.from_date",
    )
    reviews = relationship(
        "MasterReview",
        back_populates="master",
        cascade="all, delete-orphan",
    )


class MasterWorkHistory(Base):
    """
    Timeline of lounges where a master has worked.
    to_date IS NULL means currently working there.
    Production columns: from_date / to_date.
    """
    __tablename__ = "master_work_history"

    id = Column(Integer, primary_key=True)
    master_id = Column(String, ForeignKey("masters.id", ondelete="CASCADE"), nullable=False, index=True)
    lounge_id = Column(Text, nullable=False)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=True)              # NULL = currently working here

    master = relationship("Master", back_populates="work_history")


class MasterLoungeRequest(Base):
    """Pending request from a master to be attached to a lounge."""
    __tablename__ = "master_lounge_requests"

    id = Column(Integer, primary_key=True)
    master_id = Column(String, ForeignKey("masters.id", ondelete="CASCADE"), nullable=False, index=True)
    lounge_id = Column(Text, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    decided_at = Column(DateTime, nullable=True)

    master = relationship("Master")


class MasterReview(Base):
    """
    A user's review of a master.
    Production columns: master_id, user_id (author), rating, body.
    Extended with: master_response_text, master_responded_at, is_hidden.
    """
    __tablename__ = "master_reviews"

    id = Column(Integer, primary_key=True)
    master_id = Column(String, ForeignKey("masters.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # author
    rating = Column(Integer, nullable=False)           # 1-5
    body = Column(Text, nullable=True)                 # review text (production column name)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Extended columns (added via startup ALTER TABLE)
    master_response_text = Column(Text, nullable=True)
    master_responded_at = Column(DateTime, nullable=True)
    is_hidden = Column(Boolean, default=False, nullable=False, server_default="false")

    master = relationship("Master", back_populates="reviews")
    author = relationship("User", foreign_keys=[user_id])


class MasterFollower(Base):
    """master_followers join table (already in production)."""
    __tablename__ = "master_followers"

    master_id = Column(String, ForeignKey("masters.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    followed_at = Column(DateTime, default=datetime.utcnow, nullable=False)




# MARK: - Leaderboard / user medals (LOOMIX parity, S2026-05-15)
#
# Weekly and monthly podiums for top-3 mixes by likes earned in the
# corresponding period. APScheduler grants medals automatically on
# Monday 00:00 MSK (weekly) and on day-1 00:00 MSK (monthly). Backend
# also exposes a leaderboard endpoint for "right now" / period view.
#
# medal_type — 'gold' | 'silver' | 'bronze'  (rank 1, 2, 3)
# period_type — 'week' | 'month'
# period_start — Monday of the week, or first day of the month (DATE)
#
# Unique constraint (user_id, period_type, period_start, medal_type)
# guarantees idempotency: re-running the grant job inserts nothing new.
class UserMedal(Base):
    __tablename__ = "user_medals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    medal_type = Column(String(10), nullable=False)
    period_type = Column(String(10), nullable=False)
    period_start = Column(Date, nullable=False, index=True)
    mix_id = Column(Integer, ForeignKey("mixes.id"), nullable=True)
    likes_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period_type",
            "period_start",
            "medal_type",
            name="uq_user_medals_user_period_medal",
        ),
    )


class LoungeSubscription(Base):
    """
    Per-topic push subscription for a user to a lounge brand.
    Replaces the client-side UserDefaults approach — backend now knows who
    subscribed to what and can fan-out selectively.

    topic_events   — new events / promos created by the lounge
    topic_new_mix  — new mix published by the lounge or its masters
    topic_discounts — flash sales / personal offers
    topic_news     — general news (off by default — less urgent)
    """
    __tablename__ = "lounge_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id = Column(String(128), nullable=False, index=True)  # matches BrandProfile.id (slug)
    topic_events = Column(Boolean, default=True, nullable=False)
    topic_new_mix = Column(Boolean, default=True, nullable=False)
    topic_discounts = Column(Boolean, default=True, nullable=False)
    topic_news = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("user_id", "brand_id", name="uq_user_brand_sub"),)


class LoungeLoyaltyProgram(Base):
    """
    Per-venue loyalty config. One row per brand_id (slug). Created lazily —
    GET /lounges/{id}/loyalty returns defaults if no row exists, so backfill
    is not required.

    mode='percent_of_bill' → bill_percent of every receipt enters wallet
    mode='fixed' → flat bonuses for first/repeat visits + referral/birthday
    """
    __tablename__ = "lounge_loyalty_programs"
    id = Column(Integer, primary_key=True)
    brand_id = Column(String(128), nullable=False, unique=True, index=True)
    mode = Column(String(32), nullable=False, default="percent_of_bill")
    bill_percent = Column(Integer, nullable=False, default=5)
    first_visit_bonus = Column(Integer, nullable=False, default=0)
    per_visit_bonus = Column(Integer, nullable=False, default=0)
    referral_bonus = Column(Integer, nullable=False, default=0)
    birthday_multiplier = Column(Integer, nullable=False, default=2)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LoungePromo(Base):
    """Static / recurring promotional offer for a lounge.

    Examples: Happy Hour -25% weekdays before 18:00, -10% for review,
    -15% on birthday. Not a calendar event — this is a standing offer
    that applies permanently or by a recurrence rule.
    """
    __tablename__ = "lounge_promos"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String(128), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    discount_percent = Column(Integer, nullable=True)       # optional 0-100
    discount_text = Column(String(64), nullable=True)       # e.g. "-25%", "+bonus"
    icon_name = Column(String(64), nullable=True)           # SF Symbol: "clock.fill", "star.fill", "gift.fill"
    active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("brand_id", "title", name="uq_lounge_promos_brand_title"),
    )


class MasterShift(Base):
    """
    Расписание смены мастера. Мастер указывает когда он работает в каком зале —
    клиенты видят расписание на профиле, могут спланировать визит.

    starts_at / ends_at — таймстампы UTC начала/конца смены.
    Если на одну дату приходится несколько смен (смена дневная и ночная) —
    создаётся несколько записей.
    """
    __tablename__ = "master_shifts"

    id = Column(Integer, primary_key=True)
    master_id = Column(String, ForeignKey("masters.id", ondelete="CASCADE"), nullable=False, index=True)
    lounge_id = Column(Text, nullable=False)               # soft FK на brand_id
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=False)
    note = Column(Text, nullable=True)                     # «только бронь», «event night», etc.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    master = relationship("Master")


# MARK: - JWT Refresh Tokens (Phase 2, 2026-05-26)

class RefreshToken(Base):
    """
    Revocable refresh token store. One row per issued refresh token.

    token_hash  — SHA-256 hex of the raw token. Raw token is never stored.
    revoked_at  — set on logout or rotation. NULL means token is still valid.
    ip / user_agent — audit trail for session management.

    Rotation policy: on each /auth/refresh call the old token is revoked
    (revoked_at = now) and a new token is issued + inserted.
    """
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    user_agent = Column(Text, nullable=True)
    ip = Column(String(45), nullable=True)


# MARK: - CRM visit ledger (2026-05-26)

class LoungeVisit(Base):
    """
    One check-in record written by the owner QR-scanner.
    Stores financial summary for CRM analytics: bill amount, bonus awarded.
    Written in /lounges/{id}/checkin alongside LoungeGuestLoyalty update.

    brand_id     — lounge slug (same as LoungeGuestLoyalty.brand_id)
    user_id      — guest user FK
    bill_amount  — receipt total in rubles (0 if not provided / fixed-bonus mode)
    bonus_awarded — ugolki points accrued this visit
    """
    __tablename__ = "lounge_visits"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String(128), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    bill_amount = Column(Integer, nullable=False, default=0)   # rubles (int, kopecks not used)
    bonus_awarded = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    guest = relationship("User", foreign_keys=[user_id])


# MARK: - Bonus Redemption (2026-05-26)

class BonusRedemption(Base):
    """
    One bonus-points write-off executed by a lounge owner/manager.
    bonus_points = amount_rub * 10  (10 pts per 1 rub).
    balance_after is denormalised for fast audit display.
    """
    __tablename__ = "bonus_redemptions"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String(128), nullable=False, index=True)
    guest_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount_rub = Column(Integer, nullable=False)
    bonus_points = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    note = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    guest = relationship("User", foreign_keys=[guest_user_id])
    owner = relationship("User", foreign_keys=[owner_user_id])


# MARK: - Lounge Promoted Slots (2026-05-26)

class LoungePromotedSlot(Base):
    """
    Featured / promoted placement for a lounge brand.
    Active when NOW() is between starts_at and ends_at.
    region is optional — NULL means shown to all regions.
    """
    __tablename__ = "lounge_promoted_slots"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String(128), nullable=False, unique=True, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    region = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# MARK: - Lounge billing subscriptions (Sprint 1, 2026-05-27)

class LoungeBillingSubscription(Base):
    """
    Paid / trial subscription record for a lounge brand.

    tier    — start | lite | pro | network | partner
    status  — active | trialing | expired | cancelled
    payment_method — yookassa_card | manual | trial
    external_id    — YooKassa recurring subscription id (set in Sprint 2)

    One brand can have multiple historical rows. The active tier is
    determined by get_active_tier() which picks the row with
    max(expires_at) where expires_at > now() and status in (active, trialing).
    """
    __tablename__ = "lounge_billing_subscriptions"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String(128), nullable=False, index=True)
    tier = Column(String(32), nullable=False)                   # start|lite|pro|network|partner
    status = Column(String(32), nullable=False)                 # active|trialing|expired|cancelled
    started_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    payment_method = Column(String(64), nullable=True)          # yookassa_card|manual|trial
    external_id = Column(String(256), nullable=True)            # YooKassa subscription id
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())


# MARK: - Featured Slots (2026-05-27)

class FeaturedSlot(Base):
    """
    Paid featured placement for a lounge brand in /Места screen.

    slot_type — 'hero'  : top hero card (max 1 per city at a time)
                'grid'  : ribbon «Топ недели» in the regular grid
    city      — 'msk' | 'spb' | 'general' (shown to all)
    status    — 'active' | 'expired' | 'cancelled'
    payment_method — 'trial' | 'manual' | 'yookassa_card'
    """
    __tablename__ = "featured_slots"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String(128), nullable=False, index=True)
    slot_type = Column(String(32), nullable=False)               # hero | grid
    city = Column(String(64), nullable=True)                     # msk | spb | general
    starts_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    price_paid = Column(Integer, default=0, server_default="0")  # RUB
    status = Column(String(32), nullable=False, default="active", server_default="active")
    payment_method = Column(String(64), nullable=True)           # trial|manual|yookassa_card
    created_by_admin = Column(Boolean, default=False, server_default="false")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())


# MARK: - Lounge Owner Credentials (2026-05-28)

class LoungeOwnerCredentials(Base):
    """
    Admin-visible plaintext credentials for lounge owner accounts.
    Stored so the CRM can display login/password to hand off to the owner.
    password_plain is stored as-is (internal admin CRM only, never exposed
    to public API endpoints).
    """
    __tablename__ = "lounge_owner_credentials"

    brand_id = Column(String(128), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    email = Column(String, nullable=True)
    username = Column(String, nullable=True)
    password_plain = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# MARK: - Admin CRM meta for lounges (2026-05-26)

class LoungeAdminMeta(Base):
    """
    Admin-managed tier and badges for a lounge brand.
    One row per brand_id. Created lazily via PATCH endpoint.

    tier   — start | lite | pro | network | partner
    badges — JSON list: ["verified", "featured", "mix_partner", "exclusive", "top_rated"]
    notes  — internal admin note, never exposed to public endpoints
    """
    __tablename__ = "lounge_admin_meta"

    id = Column(Integer, primary_key=True)
    brand_id = Column(String(128), nullable=False, unique=True, index=True)
    tier = Column(String(32), nullable=False, default="start", server_default="start")
    badges = Column(JSON, nullable=False, default=list, server_default="[]")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
