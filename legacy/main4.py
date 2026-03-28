from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    ForeignKey, Text, UniqueConstraint, DateTime, Date, Boolean
)
from sqlalchemy.orm import (
    sessionmaker, declarative_base, relationship,
    Session, joinedload
)
import hashlib, os
from datetime import datetime, timedelta
from jose import jwt

# -------------------------------------------------------------------
# DATABASE
# -------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:pass@localhost:5433/hookahmix"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

# -------------------------------------------------------------------
# JWT
# -------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
security = HTTPBearer(auto_error=False)

REWARD_RULES = {
    "daily_login": {
        "title": "Ежедневный вход",
        "points": 5,
        "rating": 0,
        "daily_limit": 1,
    },
    "mix_created": {
        "title": "Новый микс",
        "points": 20,
        "rating": 5,
        "daily_limit": 3,
    },
    "mix_favorited": {
        "title": "Микс сохранили",
        "points": 4,
        "rating": 3,
        "daily_limit": 30,
    },
    "comment_created": {
        "title": "Комментарий отправлен",
        "points": 3,
        "rating": 0,
        "daily_limit": 10,
    },
    "comment_received": {
        "title": "Новый отзыв на микс",
        "points": 2,
        "rating": 2,
        "daily_limit": 20,
    },
}

RATING_LEVELS = [
    (0, "Новичок"),
    (100, "Миксер"),
    (300, "Блендер"),
    (700, "Мастер чаши"),
    (1500, "Hookah Legend"),
]

MIX_SLOT_RULES = [
    (0, 2),
    (100, 4),
    (300, 6),
    (700, 8),
    (1500, 10),
]

MAX_BOWL_HEAT_ATTEMPTS = 3
BOWL_HEAT_TARGET_SCORE = 75
BOWL_HEAT_DURATION_SECONDS = 20
DEFAULT_ADMIN_EMAILS = {"dorf.foto@yandex.ru"}
DEFAULT_ADMIN_USERNAMES = {"dorfden"}
DEFAULT_UNLIMITED_MIX_EMAILS = {
    "hookahplacemars@hooka3.app",
    "musthave.originals.seed@example.com",
    "neon.lounge.seed@example.com",
}
DEFAULT_UNLIMITED_MIX_USERNAMES = {
    "hookahplacemars",
    "musthave",
    "lounge_neon",
}

def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# -------------------------------------------------------------------
# MODELS
# -------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(Text)
    banned_at = Column(DateTime)

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

# -------------------------------------------------------------------
# SCHEMAS
# -------------------------------------------------------------------
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
