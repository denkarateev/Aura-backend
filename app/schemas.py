from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr


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
    email: EmailStr
    password: str
    username: Optional[str]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: int
    token: str
    username: Optional[str]


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


class LoungeCheckinIn(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    display_name: Optional[str] = None


class BundleRedemptionOut(BaseModel):
    """Info about a bundle visit redeemed during check-in, if any."""
    bundle_id: int
    tier: str
    hookah_number: int            # which one it is (1..max) or total for cityPass
    remaining: Optional[int]      # None for cityPass unlimited
    compensation_rub: int


class LoungeCheckinOut(BaseModel):
    guest: UserSearchOut
    loyalty: LoungeMyLoyaltyOut
    is_level_up: bool
    message: str
    bundle_redeemed: Optional[BundleRedemptionOut] = None


class BundleRecentVisitOut(BaseModel):
    id: int
    tier: str
    visited_at: datetime
    compensation_rub: int


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
    id: str                        # e.g. "master_alexey"
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
