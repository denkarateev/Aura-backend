from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    ForeignKey, Text, UniqueConstraint, DateTime, Boolean
)
from sqlalchemy.orm import (
    sessionmaker, declarative_base, relationship,
    Session, joinedload
)
from datetime import datetime, timedelta
from jose import jwt
import hashlib, os

# -------------------------------------------------------------------
# DATABASE
# -------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:pass@localhost:5433/hookahmix"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# -------------------------------------------------------------------
# JWT
# -------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
security = HTTPBearer(auto_error=False)

def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# -------------------------------------------------------------------
# MODELS
# -------------------------------------------------------------------

class Follow(Base):
    __tablename__ = "follows"
    id = Column(Integer, primary_key=True)
    follower_id = Column(Integer, ForeignKey("users.id"))
    following_id = Column(Integer, ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("follower_id", "following_id"),)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)

    mixes = relationship("Mix", back_populates="author")
    favorites = relationship("Favorite", back_populates="user")
    comments = relationship("Comment", back_populates="user")

class Mix(Base):
    __tablename__ = "mixes"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    name = Column(String, nullable=False)
    mood = Column(String)
    intensity = Column(Float)
    description = Column(Text)
    bowl_type = Column(String)
    packing_style = Column(String)
    bowl_image_name = Column(String)

    author = relationship("User", back_populates="mixes")
    ingredients = relationship("MixIngredient", cascade="all, delete-orphan")
    comments = relationship("Comment", cascade="all, delete-orphan")
    favorited_by = relationship("Favorite", back_populates="mix")

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

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    mix_id = Column(Integer, ForeignKey("mixes.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text)

    user = relationship("User", back_populates="comments")
    mix = relationship("Mix", back_populates="comments")

# -------------------------------------------------------------------
# SCHEMAS
# -------------------------------------------------------------------

class AuthorOut(BaseModel):
    id: int
    username: Optional[str]
    is_verified: bool
    class Config:
        from_attributes = True

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
    mood: Optional[str]
    intensity: Optional[float]
    description: Optional[str]
    bowl_type: Optional[str]
    packing_style: Optional[str]
    bowl_image_name: Optional[str]
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
    created_at: datetime
    ingredients: List[IngredientOut]
    likes_count: int
    is_liked: bool
    author: AuthorOut
    class Config:
        from_attributes = True

class UserProfileOut(BaseModel):
    id: int
    username: Optional[str]
    email: str
    created_at: datetime
    followers_count: int
    following_count: int
    total_likes: int
    mixes: List[MixOut]
    favorites: List[MixOut]
    class Config:
        from_attributes = True

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

class CommentOut(BaseModel):
    id: int
    user_id: int
    text: str
    class Config:
        from_attributes = True

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

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    if not creds:
        return None
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        return None
    return db.query(User).get(user_id)

def mix_to_out(mix: Mix, user: Optional[User], db: Session):
    likes_count = db.query(Favorite).filter(Favorite.mix_id==mix.id).count()
    is_liked = False
    if user:
        is_liked = db.query(Favorite).filter(
            Favorite.mix_id==mix.id,
            Favorite.user_id==user.id
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
        created_at=mix.created_at,
        ingredients=mix.ingredients,
        likes_count=likes_count,
        is_liked=is_liked,
        author=AuthorOut(
            id=mix.author.id,
            username=mix.author.username,
            is_verified=mix.author.is_verified
        )
    )

# -------------------------------------------------------------------
# APP
# -------------------------------------------------------------------

app = FastAPI(title="HookahMix API")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------
# AUTH
# -------------------------------------------------------------------

@app.post("/signup", response_model=LoginResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hash_password(payload.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return LoginResponse(
        user_id=user.id,
        token=create_access_token({"sub": str(user.id)}),
        username=user.username
    )

@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email==payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(400, "Invalid credentials")

    return LoginResponse(
        user_id=user.id,
        token=create_access_token({"sub": str(user.id)}),
        username=user.username
    )

# -------------------------------------------------------------------
# PROFILE
# -------------------------------------------------------------------

@app.get("/me", response_model=UserProfileOut)
def get_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(401, "Unauthorized")

    followers_count = db.query(Follow).filter(
        Follow.following_id==user.id
    ).count()

    following_count = db.query(Follow).filter(
        Follow.follower_id==user.id
    ).count()

    total_likes = db.query(Favorite).join(Mix).filter(
        Mix.author_id==user.id
    ).count()

    favorites = [f.mix for f in user.favorites]

    return UserProfileOut(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at,
        followers_count=followers_count,
        following_count=following_count,
        total_likes=total_likes,
        mixes=[mix_to_out(m, user, db) for m in user.mixes],
        favorites=[mix_to_out(m, user, db) for m in favorites],
    )
