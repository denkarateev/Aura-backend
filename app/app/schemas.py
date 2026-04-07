from datetime import datetime
from typing import List, Optional

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
    is_liked: bool
    is_author_followed: bool

    class Config:
        from_attributes = True


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


class LoungeCheckinOut(BaseModel):
    guest: UserSearchOut
    loyalty: LoungeMyLoyaltyOut
    is_level_up: bool
    message: str


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
