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
    String,
    Text,
    UniqueConstraint,
)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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
