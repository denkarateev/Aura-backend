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
