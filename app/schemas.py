from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class IngredientIn(BaseModel):
    brand: Optional[str]
    flavor: str
    percentage: int


class IngredientOut(IngredientIn):
    id: int

    class Config:
        from_attributes = True


class MixCreate(BaseModel):
    name: str
    mood: Optional[str] = None
    intensity: Optional[float] = None
    description: Optional[str] = None
    bowl_type: Optional[str] = None
    packing_style: Optional[str] = None
    bowl_image_name: Optional[str] = None
    ingredients: List[IngredientIn]
    # MARK: Mix Wizard fields (optional, default 'public' on create)
    status: Optional[Literal["public", "subscribers", "draft"]] = "public"
    lounge_id: Optional[str] = None
    tags: Optional[List[str]] = None


class MixOut(BaseModel):
    id: int
    name: str
    mood: Optional[str]
    intensity: Optional[float]
    description: Optional[str]
    bowl_type: Optional[str]
    packing_style: Optional[str]
    bowl_image_name: Optional[str]
    author_id: Optional[int]
    author_username: Optional[str]
    created_at: Optional[datetime]
    ingredients: List[IngredientOut]
    likes_count: int
    comments_count: int = 0
    is_liked: bool
    is_author_followed: bool
    # MARK: Mix Wizard fields
    status: str = "public"
    lounge_id: Optional[str] = None
    tags: List[str] = []
    # True when lounge_id has mix_partner badge (admin CRM)
    lounge_partner_badge: bool = False

    class Config:
        from_attributes = True


# MARK: Mix Wizard — generate (rule-based AI)

class MixGenerateIn(BaseModel):
    """
    Brief from the iOS Mix Wizard. Mood drives flavor pool selection,
    strength drives ingredient count, brands narrows the candidate set.
    """
    mood: Literal["berry", "citrus", "fresh", "fruit", "warm", "mint"]
    strength: int                              # 1-10
    brands: Optional[List[str]] = None         # selected brand ids; empty/None = AI picks
    occasion: Optional[str] = None             # free text from chip set


class MixGenerateOut(BaseModel):
    """
    Generated suggestion. NOT persisted — caller decides whether to POST /mixes
    with this payload.
    """
    name: str
    description: str
    ingredients: List[IngredientIn]
    mood: str
    intensity: float
    tags: List[str]


class CommentOut(BaseModel):
    id: int
    mix_id: int
    user_id: int
    user_username: Optional[str] = None
    text: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProfileCommentOut(CommentOut):
    mix_name: Optional[str] = None


class UserProgressOut(BaseModel):
    points: int
    rating: int
    streak_days: int
    level_title: str
    next_level_rating: int
    mixes_used: int
    max_mix_slots: Optional[int]
    mixes_remaining: Optional[int]
    has_unlimited_mix_slots: bool


class UserActivityOut(BaseModel):
    id: int
    event_type: str
    title: str
    description: Optional[str]
    points_delta: int
    rating_delta: int
    created_at: datetime


class BowlHeatGameStateOut(BaseModel):
    title: str
    subtitle: str
    attempts_used: int
    attempts_left: int
    max_attempts: int
    best_score_today: int
    best_tier_today: Optional[str] = None
    target_score: int
    duration_seconds: int
    reward_hint: str
    can_play: bool
    last_played_at: Optional[datetime] = None


class BowlHeatPlayIn(BaseModel):
    score: int
    sweet_spot_seconds: float
    overheat_seconds: float
    taps_count: int
    duration_seconds: float


class BowlHeatPlayOut(BaseModel):
    score: int
    tier: str
    result_title: str
    result_message: str
    points_awarded: int
    rating_awarded: int
    is_new_best: bool
    state: BowlHeatGameStateOut


class FollowUserOut(BaseModel):
    id: int
    username: Optional[str]
    mixes_count: int
    likes_count: int
    latest_mix_id: Optional[int] = None
    latest_mix_name: Optional[str] = None
    latest_mix_bowl_image_name: Optional[str] = None
    latest_mix_created_at: Optional[datetime] = None
    is_following: bool


class UserSearchOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: str
    username: Optional[str]
    is_admin: bool
    is_banned: bool
    ban_reason: Optional[str]
    mixes: List[MixOut]
    favorites: List[MixOut]
    comments: List[ProfileCommentOut]
    progress: UserProgressOut
    activity_feed: List[UserActivityOut]
    daily_game: BowlHeatGameStateOut
    followers_count: int
    following_count: int
    following_users: List[FollowUserOut]


class SignupRequest(BaseModel):
    # email теперь str (а не EmailStr) — позволяет iOS показать
    # человеческий «введи валидный email» через нашу backend-валидацию,
    # а не неинформативный 422 от pydantic. Backend сам проверяет формат.
    email: str
    password: str
    username: Optional[str] = None  # default добавлен — раньше Optional без = None требовал поле
    display_name: Optional[str] = None
    phone: Optional[str] = None
    referrer_code: Optional[str] = None  # ON-8: referral reward (200 угольков приглашающему)
    accepted_terms: bool = False  # 152-FZ / App Store: user must accept ToU + Privacy Policy


class LoginRequest(BaseModel):
    # Принимаем email ИЛИ username — backend (main.py:login) сам ищет
    # юзера по обоим полям. EmailStr убран ради username-логина для
    # lounge-owner аккаунтов (gallery_secret_lounge, и т.п.).
    email: str
    password: str


class LoginResponse(BaseModel):
    user_id: int
    token: str
    username: Optional[str]
    # Refresh token fields — present for clients that support rotation.
    # Omitted (None) only on very old code paths; new clients always get them.
    refresh_token: Optional[str] = None
    access_expires_in: Optional[int] = None  # seconds


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_in: int  # seconds


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None  # invalidate specific session; None = current


class CommentIn(BaseModel):
    text: str


class UserUpdate(BaseModel):
    username: Optional[str]
    email: Optional[EmailStr]


class FollowToggleOut(BaseModel):
    user_id: int
    is_following: bool


class VoteMixOut(BaseModel):
    id: int
    name: str
    lounge: str
    percentage: float
    image_name: Optional[str] = None
    cover_url: str = ""

    class Config:
        from_attributes = True


class MonthlyFlavorOut(BaseModel):
    title: str
    subtitle: str
    remaining_time: str
    progress: float
    sponsor_brand: Optional[str] = None
    featured_flavor: Optional[str] = None
    challenge_title: Optional[str] = None
    challenge_reward: Optional[str] = None
    cta_title: Optional[str] = None
    mixes: List[VoteMixOut]


class AdminDashboardStatsOut(BaseModel):
    total_users: int
    banned_users: int
    total_mixes: int
    total_comments: int
    total_favorites: int


class AdminUserRowOut(BaseModel):
    id: int
    email: str
    username: Optional[str]
    is_admin: bool
    is_banned: bool
    ban_reason: Optional[str]
    mixes_count: int
    followers_count: int
    favorites_received: int
    latest_mix_name: Optional[str] = None
    latest_mix_created_at: Optional[datetime] = None


class AdminMixRowOut(BaseModel):
    id: int
    name: str
    author_id: Optional[int]
    author_username: Optional[str]
    created_at: Optional[datetime]
    likes_count: int
    comments_count: int
    ingredients_count: int


class AdminDashboardOut(BaseModel):
    stats: AdminDashboardStatsOut
    users: List[AdminUserRowOut]
    recent_mixes: List[AdminMixRowOut]


class AdminBanIn(BaseModel):
    reason: Optional[str] = None


class LoungeProgramIn(BaseModel):
    title: str
    summary: str
    base_discount_percent: int
    welcome_offer_title: str
    welcome_offer_body: str


class LoungeProgramOut(LoungeProgramIn):
    brand_id: str
    updated_at: Optional[datetime] = None


class LoungeGuestRecordIn(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    favorite_order: Optional[str] = None
    average_check: Optional[int] = None
    visit_count: int = 1
    personal_tier_title: Optional[str] = None
    personal_discount_percent: Optional[int] = None
    personal_offer_title: Optional[str] = None
    personal_offer_body: Optional[str] = None
    note: Optional[str] = None


class LoungeGuestRecordOut(BaseModel):
    id: int
    user_id: int
    username: str
    display_name: Optional[str] = None
    favorite_order: Optional[str] = None
    average_check: Optional[int] = None
    visit_count: int
    personal_tier_title: Optional[str] = None
    personal_discount_percent: Optional[int] = None
    personal_offer_title: Optional[str] = None
    personal_offer_body: Optional[str] = None
    note: Optional[str] = None
    updated_at: Optional[datetime] = None


class LoungeTierOut(BaseModel):
    title: str
    discount_percent: int
    discount_text: str
    benefit: str
    next_goal: Optional[int] = None


class LoungeMyLoyaltyOut(BaseModel):
    brand_id: str
    visit_count: int
    last_visit_at: Optional[datetime] = None
    tier: LoungeTierOut
    program: LoungeProgramOut
    personalization: Optional[LoungeGuestRecordOut] = None
    # Юзер: «сколько бонусов в заведении не пишется только визит».
    # Per-lounge баланс уже хранится в lounge_guest_loyalties.bonus_balance
    # (рефактор 3950f5c). Добавлен в response чтобы iOS показывал реальные
    # цифры рядом с числом визитов.
    bonus_balance: int = 0
    bonus_rub: int = 0   # bonus_balance // 10 для удобства UI


class LoungeCheckinIn(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    master_id: Optional[str] = None
    bill_amount: Optional[float] = None  # rubles — required only for percent_of_bill mode


class BundleRedemptionOut(BaseModel):
    """Info about a bundle visit redeemed during check-in, if any."""
    bundle_id: int
    tier: str
    hookah_number: int            # which one it is (1..max) or total for cityPass
    remaining: Optional[int]      # None for cityPass unlimited
    compensation_rub: int
    master_id: Optional[str] = None


class LoungeCheckinOut(BaseModel):
    guest: UserSearchOut
    loyalty: LoungeMyLoyaltyOut
    is_level_up: bool
    message: str
    bundle_redeemed: Optional[BundleRedemptionOut] = None
    bonus: int = 0              # points accrued this checkin
    is_first_visit: bool = False
    mode: str = "percent_of_bill"  # loyalty program mode used


class BundleRecentVisitOut(BaseModel):
    id: int
    tier: str
    visited_at: datetime
    compensation_rub: int
    master_id: Optional[str] = None


# MARK: - Lounge events / promos

class EventIn(BaseModel):
    title: str
    subtitle: Optional[str] = None
    kind: str = "promo"
    mood: str = "warm"
    lounge_id: Optional[str] = None
    venue_title: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    recurrence: Optional[dict] = None
    cover_image_url: Optional[str] = None
    price_text: Optional[str] = None
    booking_url: Optional[str] = None
    tags: List[str] = []


class EventOut(EventIn):
    id: str
    going_count: int = 0
    is_going: bool = False


class EventRSVPIn(BaseModel):
    going: bool = True


class EventRSVPOut(BaseModel):
    status: str = "ok"
    going: bool
    going_count: int


class LoungeAnalyticsDayOut(BaseModel):
    day_key: str
    profile_views: int
    qr_shows: int
    qr_checkins: int
    loyalty_assignments: int


class LoungeAnalyticsOut(BaseModel):
    brand_id: str
    profile_views: int
    qr_shows: int
    qr_checkins: int
    loyalty_guests_count: int
    total_visits: int
    today_visits: int
    assigned_guests_count: int
    offers_count: int
    # Bundle redemption stats — populated when the caller manages this lounge
    bundle_visits_total: int = 0
    bundle_visits_this_month: int = 0
    bundle_compensation_pending_rub: int = 0
    bundle_compensation_settled_rub: int = 0
    bundle_recent_visits: List[BundleRecentVisitOut] = []
    max_assigned_discount: int
    timeline: List[LoungeAnalyticsDayOut]


class StatusOut(BaseModel):
    status: str
    message: Optional[str] = None


class WalletConnectIn(BaseModel):
    ton_address: str

class WalletBalanceOut(BaseModel):
    user_id: int
    ton_address: Optional[str] = None
    ugolki_balance: int
    hooka_balance: float
    conversion_rate: int = 100

class WalletMintOut(BaseModel):
    success: bool
    amount: int
    new_ugolki_balance: int
    new_hooka_balance: float
    tx_hash: Optional[str] = None

class WalletBurnOut(BaseModel):
    success: bool
    amount: int
    reason: str
    new_ugolki_balance: int
    new_hooka_balance: float



class DuelCreateIn(BaseModel):
    brand_id: str

class DuelCreateOut(BaseModel):
    duel_id: str
    join_code: str
    base_discount: int
    duel_discount: int
    status: str

class DuelStateOut(BaseModel):
    duel_id: str
    brand_id: str
    guest_username: Optional[str] = None
    host_username: Optional[str] = None
    status: str
    guest_score: int
    host_score: int
    winner_id: Optional[int] = None
    base_discount: int
    duel_discount: int

class DuelJoinIn(BaseModel):
    join_code: str


# MARK: - Bundle subscription schemas

class BundlePaymentCreateIn(BaseModel):
    tier: str  # "five" | "ten" | "cityPass" | "group"


class BundlePaymentCreateOut(BaseModel):
    payment_id: str
    confirmation_url: str
    amount_rub: int


class BundlePaymentStatusOut(BaseModel):
    payment_id: str
    status: str          # pending | waiting_for_capture | succeeded | canceled
    paid: bool
    bundle_id: Optional[int] = None  # set once /bundles/purchase has finalised


class BundleVisitOut(BaseModel):
    id: int
    brand_id: str
    visited_at: datetime
    compensation_rub: int


class BundleOut(BaseModel):
    id: int
    tier: str
    price_rub: int
    compensation_per_visit_rub: int
    max_visits: int  # 0 means unlimited (cityPass)
    started_at: datetime
    expires_at: datetime
    status: str
    visits: List[BundleVisitOut] = []


class BundleListOut(BaseModel):
    active: List[BundleOut]
    past: List[BundleOut]


# MARK: - Device token

class DeviceTokenIn(BaseModel):
    token: str
    platform: str = "ios"       # ios | android
    app_version: Optional[str] = None


# MARK: - Apple Sign-In

class AppleSignInIn(BaseModel):
    identity_token: str         # JWT from Sign in with Apple
    full_name: Optional[str] = None  # only on first auth per Apple
    email: Optional[str] = None      # only on first auth per Apple


class AppleSignInOut(BaseModel):
    user_id: int
    token: str
    username: Optional[str] = None
    is_new_user: bool


# MARK: - Lounge assets (media + structured info)

class LoungeAssetsIn(BaseModel):
    """Payload for PUT /lounges/{brand_id}/assets — manager sets media + info."""
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None
    photos: Optional[List[str]] = None          # replaces the whole gallery
    info: Optional[dict] = None                  # cuisine/atmosphere/signature_mix/vibe/...


class LoungeAssetsOut(BaseModel):
    """Response for GET /lounges/{brand_id}/assets — returned to iOS."""
    brand_id: str
    avatar_url: Optional[str] = None
    cover_url: Optional[str] = None
    photos: List[str] = []
    info: dict = {}
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TelegramLinkCodeOut(BaseModel):
    """
    Response for POST /me/telegram/link-code

    Manager copies `code` and sends `/start <code>` to the bot.
    The code is valid for 10 minutes; expired codes return 410 on bot side.
    """
    code: str
    expires_at: datetime
    bot_username: str
    deep_link: str  # https://t.me/<bot>?start=<code>


class TelegramLinkStatusOut(BaseModel):
    """Response for GET /me/telegram/status"""
    linked: bool
    telegram_username: Optional[str] = None
    verified_at: Optional[datetime] = None


class LoungeBusynessOut(BaseModel):
    """Response for GET /lounges/{brand_id}/busyness"""
    brand_id: str
    percent: int                        # 0-100
    level: str                          # quiet | moderate | busy | peak
    source: str                         # yandex_maps | dgis | checkins_last_hour | mock_hourly
    updated_at: Optional[datetime] = None  # when yandex_maps source, timestamp of last override


class LoungeRefreshBusynessIn(BaseModel):
    """
    Payload for POST /lounges/{brand_id}/refresh-busyness

    Manager or admin manually overrides the busyness % for a lounge.
    This is the primary mechanism until a real-time Yandex scraper daemon is available.

    Fields:
      percent         — current busyness 0-100 (required)
      yandex_org_id   — optional: store the Yandex Maps org ID for future daemon use
                        (numeric string, found in yandex.ru/maps/org/.../ORGID/)
      dgis_branch_id  — optional: store the 2GIS branch ID for automatic busyness fetching.
                        Found in 2gis.ru URL: 2gis.ru/.../firm/<BRANCH_ID>/
                        When set, GET /busyness will auto-fetch via 2GIS API
                        before falling back to checkins or mock.
    """
    percent: int
    yandex_org_id: Optional[str] = None
    dgis_branch_id: Optional[str] = None

    class Config:
        # Validate percent range
        pass


# MARK: - Masters domain schemas

class MasterWorkplaceOut(BaseModel):
    id: int
    lounge_id: str
    started_at: Optional[datetime] = None  # serialised as ISO string
    ended_at: Optional[datetime] = None
    is_current: bool

    class Config:
        from_attributes = True


class MasterOut(BaseModel):
    id: str
    handle: str
    display_name: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    current_lounge_id: Optional[str] = None
    rating: float
    followers_count: int
    mixes_count: int
    reviews_count: int
    is_verified: bool
    is_following: bool = False
    work_history: List[MasterWorkplaceOut] = []

    class Config:
        from_attributes = True


class MasterListOut(BaseModel):
    items: List[MasterOut]
    total: int
    page: int
    page_size: int


class MasterCreateIn(BaseModel):
    id: Optional[str] = None       # авто-генерится из handle если не задан
    handle: str
    display_name: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    current_lounge_id: Optional[str] = None
    mixes_count: int = 0
    followers_count: int = 0
    rating: float = 0.0


class MasterUpdateIn(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    current_lounge_id: Optional[str] = None


# Work history
class MasterWorkHistoryAddIn(BaseModel):
    lounge_id: str
    started_at: str                # ISO date string "YYYY-MM-DD"


class MasterWorkHistoryAddOut(BaseModel):
    status: str
    id: int
    master_id: str
    lounge_id: str


class MasterLoungeRequestIn(BaseModel):
    lounge_id: str


class MasterLoungeRequestOut(BaseModel):
    id: int
    master_id: str
    master_display_name: str
    master_handle: str
    master_avatar_url: Optional[str] = None
    lounge_id: str
    status: str
    requested_by: Optional[int] = None
    created_at: datetime
    decided_at: Optional[datetime] = None


# Reviews
class MasterReviewCreateIn(BaseModel):
    rating: int                    # 1-5
    text: str
    visit_id: Optional[int] = None


class MasterReviewOut(BaseModel):
    id: int
    master_id: str
    author_user_id: int
    author_display_name: Optional[str] = None
    author_avatar_url: Optional[str] = None
    rating: int
    text: str
    created_at: datetime
    master_response_text: Optional[str] = None
    master_responded_at: Optional[datetime] = None
    is_hidden: bool

    class Config:
        from_attributes = True


class MasterReviewsListOut(BaseModel):
    items: List[MasterReviewOut]
    total: int
    page: int
    page_size: int


class MasterResponseCreateIn(BaseModel):
    text: str


class MasterResponseOut(BaseModel):
    review_id: int
    master_response_text: str
    master_responded_at: datetime


class MasterGuestVisitOut(BaseModel):
    id: int
    brand_id: str
    guest_user_id: int
    guest_username: str
    visited_at: datetime
    bundle_redeemed: bool = False
    compensation_rub: int = 0


class MasterGuestStatsOut(BaseModel):
    master_id: str
    total_visits: int
    unique_guests: int
    repeat_guests: int
    bundle_redemptions: int
    compensation_rub: int
    recent_visits: List[MasterGuestVisitOut]


# MARK: - Master Shifts (расписание смен)

class MasterShiftCreateIn(BaseModel):
    """Мастер создаёт смену на определённой площадке.
    Время в ISO 8601 — клиент шлёт UTC."""
    lounge_id: str
    starts_at: datetime
    ends_at: datetime
    note: Optional[str] = None


class MasterShiftOut(BaseModel):
    id: int
    master_id: str
    lounge_id: str
    starts_at: datetime
    ends_at: datetime
    note: Optional[str] = None
    created_at: datetime
    # Embedded для агрегированных запросов /shifts — клиент не зовёт каждого
    # мастера отдельно. На /masters/{id}/shifts эти поля тоже приходят но
    # дубликаты безвредны.
    master_handle: Optional[str] = None
    master_display_name: Optional[str] = None
    master_avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class MasterShiftsListOut(BaseModel):
    items: List[MasterShiftOut]
    total: int


# MARK: - Lounge push subscriptions (per-topic)

class LoungeSubscriptionIn(BaseModel):
    """Body for PUT /lounges/{brand_id}/subscription.
    All fields are optional — omitted fields keep their current value on upsert.
    Default values mirror the iOS BrandSubscriptionSheet defaults.
    """
    topic_events: Optional[bool] = True
    topic_new_mix: Optional[bool] = True
    topic_discounts: Optional[bool] = True
    topic_news: Optional[bool] = False


class LoungeSubscriptionDTO(BaseModel):
    brand_id: str
    topic_events: bool = True
    topic_new_mix: bool = True
    topic_discounts: bool = True
    topic_news: bool = False

    class Config:
        from_attributes = True


# MARK: - Per-venue loyalty program (configurable by lounge owner)

class LoungeLoyaltyProgramOut(BaseModel):
    brand_id: str
    mode: str               # "percent_of_bill" | "fixed"
    bill_percent: int = 5
    first_visit_bonus: int = 0
    per_visit_bonus: int = 0
    referral_bonus: int = 0
    birthday_multiplier: int = 2

    class Config:
        from_attributes = True


class LoungeLoyaltyProgramIn(BaseModel):
    mode: str               # required, "percent_of_bill" | "fixed"
    bill_percent: Optional[int] = None       # 0-100
    first_visit_bonus: Optional[int] = None  # >=0
    per_visit_bonus: Optional[int] = None    # >=0
    referral_bonus: Optional[int] = None     # >=0
    birthday_multiplier: Optional[int] = None  # 1-10


# MARK: - Account deletion (App Store 5.1.1(v))

class AccountDeleteOut(BaseModel):
    status: str
    user_id: int


# MARK: - Master avatar upload

class MasterAvatarUploadIn(BaseModel):
    """iOS sends the file as base64 in JSON, not multipart. See
    `MixAPI.uploadMyMasterAvatar` for the reference client."""
    file_name: Optional[str] = "avatar.jpg"
    mime_type: Optional[str] = "image/jpeg"
    data_base64: str


# MARK: - Lounge cover / avatar upload (owner-only)

class LoungeImageUploadIn(BaseModel):
    """Payload for POST /lounges/{brand_id}/cover and /avatar.
    iOS posts a base64-encoded JPEG/PNG; backend decodes via Pillow, resizes,
    and stores under /app/static/lounges/."""
    file_name: Optional[str] = "lounge.jpg"
    mime_type: Optional[str] = "image/jpeg"
    # Accept both `image_base64` (per spec) and `data_base64` (matches the
    # master-avatar contract) so the iOS team can pick whichever they prefer.
    image_base64: Optional[str] = None
    data_base64: Optional[str] = None

    @property
    def payload_b64(self) -> Optional[str]:
        return self.image_base64 or self.data_base64


# MARK: - Tobacco flavors catalog

class TobaccoFlavorOut(BaseModel):
    id: int
    brand: str
    name: str
    category: Optional[str] = None
    strength: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    color: Optional[str] = None

    class Config:
        from_attributes = True


class TobaccoFlavorListOut(BaseModel):
    items: List[TobaccoFlavorOut]
    total: int
    limit: int
    offset: int


# MARK: - Tobacco brands catalog

class TobaccoBrandOut(BaseModel):
    brand: str
    category: str
    flavor_count: int


class TobaccoBrandListOut(BaseModel):
    items: List[TobaccoBrandOut]
    total: int


class TobaccoBrandFlavorsOut(BaseModel):
    brand: str
    category: str
    flavors: List[str]
    total: int


# MARK: - Tobacco mix templates

class TobaccoMixTemplateIngredientOut(BaseModel):
    brand: Optional[str] = None
    flavor: Optional[str] = None
    flavor_id: Optional[int] = None
    percentage: Optional[int] = None
    position: int


class TobaccoMixTemplateOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    primary_brand: str
    mood: Optional[str] = None
    strength_score: Optional[int] = None
    image_url: Optional[str] = None
    ingredients: List[TobaccoMixTemplateIngredientOut]


class TobaccoMixTemplateListOut(BaseModel):
    items: List[TobaccoMixTemplateOut]
    total: int
    limit: int
    offset: int


# MARK: - Leaderboard / Medals (LOOMIX parity, S2026-05-15)

class LeaderboardEntryOut(BaseModel):
    """One row on the Top забивок podium / list."""
    rank: int
    medal: Optional[Literal["gold", "silver", "bronze"]] = None
    mix_id: int
    mix_name: str
    mix_cover_url: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    likes_count: int


class LeaderboardOut(BaseModel):
    period: Literal["week", "month"]
    period_start: datetime
    period_end: datetime
    category: str = "mixes"
    entries: List[LeaderboardEntryOut]


class MedalCountsOut(BaseModel):
    gold: int = 0
    silver: int = 0
    bronze: int = 0


class UserPublicStatsOut(BaseModel):
    posts_count: int
    likes_received: int
    comments_made: int
    followers_count: int
    following_count: int
    medals: MedalCountsOut


class UserMedalOut(BaseModel):
    id: int
    medal_type: Literal["gold", "silver", "bronze"]
    period_type: Literal["week", "month"]
    period_start: datetime
    likes_count: int
    mix_id: Optional[int] = None
    mix_name: Optional[str] = None
    mix_cover_url: Optional[str] = None
    created_at: datetime


class MedalBackfillOut(BaseModel):
    period_type: Literal["week", "month"]
    period_start: datetime
    granted: int
    skipped_existing: int
    entries: List[LeaderboardEntryOut]


# MARK: - Lounge promos (afisha / aktsii)

class LoungePromoOut(BaseModel):
    id: int
    brand_id: str
    title: str
    description: Optional[str] = None
    discount_percent: Optional[int] = None
    discount_text: Optional[str] = None
    icon_name: Optional[str] = None
    active: bool
    sort_order: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoungePromoIn(BaseModel):
    title: str
    description: Optional[str] = None
    discount_percent: Optional[int] = None
    discount_text: Optional[str] = None
    icon_name: Optional[str] = None
    active: bool = True
    sort_order: int = 0


class LoungePromoUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    discount_percent: Optional[int] = None
    discount_text: Optional[str] = None
    icon_name: Optional[str] = None
    active: Optional[bool] = None
    sort_order: Optional[int] = None


class LoungePromoListOut(BaseModel):
    items: List[LoungePromoOut]
    total: int


# MARK: - CRM schemas (2026-05-26)

class HourBucket(BaseModel):
    hour: int
    count: int


class WeekdayBucket(BaseModel):
    weekday: int   # 0=Mon, 6=Sun (ISO)
    count: int


class LoungeCrmStatsOut(BaseModel):
    period: str
    visits_count: int
    unique_guests: int
    total_revenue: int
    avg_bill: int
    repeat_rate: float
    new_guests: int
    top_hours: List[HourBucket]
    top_weekdays: List[WeekdayBucket]


class LoungeCrmRegularOut(BaseModel):
    user_id: int
    username: str
    avatar_url: Optional[str] = None
    visits_count: int
    total_spent: int
    last_visit_at: datetime
    avg_bill: int
    bonus_balance: int


class LoungeCrmRegularsOut(BaseModel):
    items: List[LoungeCrmRegularOut]
    total: int
    limit: int
    offset: int


class GuestVisitRowOut(BaseModel):
    id: int
    bill_amount: int
    bonus_awarded: int
    created_at: datetime


class LoungeCrmGuestCardOut(BaseModel):
    user_id: int
    username: str
    avatar_url: Optional[str] = None
    first_visit_at: datetime
    last_visit_at: datetime
    visits_count: int
    total_spent: int
    avg_bill: int
    bonus_balance: int
    favorite_brands: Optional[List[str]] = None
    last_mixes: List[dict] = []
    recent_visits: List[GuestVisitRowOut] = []


# MARK: - Bonus Redemption (2026-05-26)

class GuestBalanceOut(BaseModel):
    user_id: int
    username: str
    avatar_url: Optional[str] = None
    bonus_balance: int        # текущий баланс в баллах
    rub_equivalent: int       # bonus_balance // 10
    total_earned: int         # всего начислено баллов
    total_redeemed: int       # всего списано баллов
    last_visit_at: Optional[datetime] = None


class RedeemIn(BaseModel):
    guest_user_id: int
    amount_rub: int           # сколько рублей списываем (мин 200)
    note: Optional[str] = None


class RedemptionRowOut(BaseModel):
    id: int
    brand_id: str
    guest_user_id: int
    guest_username: Optional[str] = None
    owner_user_id: int
    amount_rub: int
    bonus_points: int
    balance_after: int
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class RedemptionListOut(BaseModel):
    items: List[RedemptionRowOut]
    total: int


# MARK: - Promoted Lounges (2026-05-26)

class PromotedLoungeOut(BaseModel):
    brand_id: str
    starts_at: datetime
    ends_at: datetime
    region: Optional[str] = None


class PromotedListOut(BaseModel):
    items: List[PromotedLoungeOut]
    total: int


class PromotedSlotIn(BaseModel):
    brand_id: str
    starts_at: datetime
    ends_at: datetime
    region: Optional[str] = None


# MARK: - Featured Slots (2026-05-27)

class FeaturedSlotOut(BaseModel):
    id: int
    brand_id: str
    slot_type: str
    city: Optional[str] = None
    starts_at: datetime
    expires_at: datetime
    price_paid: int = 0
    status: str
    payment_method: Optional[str] = None
    created_by_admin: bool = False
    created_at: datetime
    remaining_days: Optional[int] = None   # computed, only in admin list

    class Config:
        from_attributes = True


class FeaturedSlotIn(BaseModel):
    """Admin: create a new featured slot."""
    slot_type: str                          # hero | grid
    city: str = "general"                  # msk | spb | general
    days: int                               # duration from now
    price_paid: int = 0
    payment_method: str = "manual"         # trial | manual | yookassa_card


class FeaturedFeedOut(BaseModel):
    """Public /lounges/featured response consumed by iOS."""
    hero: Optional[FeaturedSlotOut] = None
    grid: List[FeaturedSlotOut] = []


# MARK: - Per-lounge bonus balances for current user (2026-05-26)

class LoungeMyBonusItemOut(BaseModel):
    brand_id: str
    brand_title: str
    bonus_balance: int
    rub_equivalent: int
    visit_count: int
    last_visit_at: Optional[datetime] = None


class LoungeMyBonusesOut(BaseModel):
    items: List[LoungeMyBonusItemOut]
    total_balance: int
    total_rub: int


# MARK: - Brand Analytics (2026-05-26)

class FlavorPopularity(BaseModel):
    flavor: str
    mixes_count: int
    avg_percentage: float


class RegionBucket(BaseModel):
    region: str
    mixes_count: int


class BrandAnalyticsOut(BaseModel):
    brand: str
    total_mixes_using: int
    total_likes_on_those_mixes: int
    unique_authors: int
    top_flavors: List[FlavorPopularity]
    growth_30d: float
    region_split: List[RegionBucket]


# MARK: - Admin CRM lounge management (2026-05-26)

VALID_LOUNGE_TIERS = {"start", "lite", "pro", "network", "partner"}
VALID_LOUNGE_BADGES = {"verified", "featured", "mix_partner", "exclusive", "top_rated"}


class LoungeAdminMetaOut(BaseModel):
    brand_id: str
    tier: str
    badges: List[str]
    notes: Optional[str] = None


class LoungeAdminMetaIn(BaseModel):
    tier: Optional[str] = None       # one of VALID_LOUNGE_TIERS; None = keep current
    badges: Optional[List[str]] = None  # full replace; None = keep current
    notes: Optional[str] = None


class LoungeAdminListItemOut(BaseModel):
    brand_id: str
    tier: str
    badges: List[str]
    visits_last_30d: int
    bonus_outstanding: int    # SUM lounge_guest_loyalties.bonus_balance
    promos_active: int


# Public (no auth) — subset without notes
class LoungePublicMetaOut(BaseModel):
    brand_id: str
    tier: str
    badges: List[str]
    subscription_active: bool = False
    is_featured_now: bool = False


# MARK: - Lounge billing subscription schemas (Sprint 1, 2026-05-27)

class LoungeBillingSubscriptionOut(BaseModel):
    id: int
    brand_id: str
    tier: str
    status: str
    started_at: datetime
    expires_at: datetime
    payment_method: Optional[str] = None
    external_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LoungeBillingSubscriptionGrantIn(BaseModel):
    """Admin: grant or extend a subscription."""
    tier: str                       # start|lite|pro|network|partner
    days: int                       # duration to add from now (or from current expires_at)
    payment_method: str = "manual"  # yookassa_card|manual|trial


class LoungeCheckoutIn(BaseModel):
    """Body for POST /lounges/{brand_id}/subscription/checkout (stub)."""
    tier: str                       # start|lite|pro|network|partner


class LoungeCheckoutOut(BaseModel):
    checkout_url: str


class UpgradeRequiredOut(BaseModel):
    error: str = "upgrade_required"
    required_tier: str
    current_tier: str


# MARK: CRM Heatmap (2026-05-27)
class LoungeCRMHeatmapCellOut(BaseModel):
    dow: int        # 0=Sun, 1=Mon..6=Sat (Postgres EXTRACT DOW default)
    hour: int       # 0-23
    visit_count: int


class LoungeCRMHeatmapOut(BaseModel):
    cells: List[LoungeCRMHeatmapCellOut]
    total_visits: int
    days_back: int
    tz_offset_min: int


# MARK: - Lounge Highlights (2026-05-28)

class HighlightCardIn(BaseModel):
    title: str
    subtitle: str
    image_url: str


class HighlightCardOut(BaseModel):
    id: str
    title: str
    subtitle: str
    image_url: str


class LoungeHighlightsIn(BaseModel):
    highlights: List[HighlightCardIn]


class LoungeHighlightsOut(BaseModel):
    highlights: List[HighlightCardOut]


class LoungeHighlightPhotoOut(BaseModel):
    url: str


# MARK: - Lounge Broadcast Push (2026-05-28)

class LoungePushIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    body: str = Field(..., min_length=1, max_length=200)
