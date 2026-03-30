from datetime import datetime

from sqlalchemy import (
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
