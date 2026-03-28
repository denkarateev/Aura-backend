from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    sessionmaker,
    declarative_base,
    relationship,
    Session,
)
import hashlib
import os
from datetime import datetime, timedelta
from jose import jwt, JWTError

# -------------------------------------------------------------------
# DATABASE
# -------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:pass@localhost:5433/hookahmix",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

# -------------------------------------------------------------------
# JWT
# -------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

security = HTTPBearer()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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

    mixes = relationship("Mix", back_populates="author")
    favorites = relationship("Favorite", back_populates="user")
    comments = relationship("Comment", back_populates="user")


class Mix(Base):
    __tablename__ = "mixes"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)

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

    @property
    def likes_count(self) -> int:
        return len(self.favorited_by)


class MixIngredient(Base):
    __tablename__ = "mix_ingredients"

    id = Column(Integer, primary_key=True)
    mix_id = Column(Integer, ForeignKey("mixes.id"), nullable=False)
    brand = Column(String)
    flavor = Column(String, nullable=False)
    percentage = Column(Integer, nullable=False)


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
    text = Column(Text, nullable=False)

    user = relationship("User", back_populates="comments")
    mix = relationship("Mix", back_populates="comments")


# -------------------------------------------------------------------
# SCHEMAS (Pydantic v2)
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
    ingredients: List[IngredientOut]
    likes_count: int

    class Config:
        from_attributes = True


class CommentOut(BaseModel):
    id: int
    mix_id: int
    user_id: int
    text: str

    class Config:
        from_attributes = True


class CommentWithMixOut(BaseModel):
    id: int
    mix_id: int
    mix_name: str
    text: str


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


class UserProfileOut(BaseModel):
    id: int
    email: EmailStr
    username: Optional[str]
    mixes: List[MixOut]
    favorites: List[MixOut]
    comments: List[CommentWithMixOut]

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


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hash_: str) -> bool:
    return hash_password(password) == hash_


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


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
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return LoginResponse(
        user_id=user.id,
        token=create_access_token({"sub": str(user.id)}),
        username=user.username,
    )


@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(400, "Invalid credentials")

    return LoginResponse(
        user_id=user.id,
        token=create_access_token({"sub": str(user.id)}),
        username=user.username,
    )


# -------------------------------------------------------------------
# PROFILE
# -------------------------------------------------------------------

@app.get("/me", response_model=UserProfileOut)
def me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comments = [
        CommentWithMixOut(
            id=c.id,
            mix_id=c.mix_id,
            mix_name=c.mix.name,
            text=c.text,
        )
        for c in user.comments
    ]

    return UserProfileOut(
        id=user.id,
        email=user.email,
        username=user.username,
        mixes=user.mixes,
        favorites=[f.mix for f in user.favorites],
        comments=comments,
    )


# -------------------------------------------------------------------
# MIXES
# -------------------------------------------------------------------

@app.post("/mixes", response_model=MixOut)
def create_mix(
    payload: MixCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mix = Mix(author_id=user.id, **payload.dict(exclude={"ingredients"}))
    db.add(mix)
    db.flush()

    for ing in payload.ingredients:
        db.add(MixIngredient(mix_id=mix.id, **ing.dict()))

    db.commit()
    db.refresh(mix)
    return mix


@app.get("/mixes", response_model=List[MixOut])
def list_mixes(db: Session = Depends(get_db)):
    return db.query(Mix).all()


@app.get("/mixes/{mix_id}", response_model=MixOut)
def get_mix(mix_id: int, db: Session = Depends(get_db)):
    mix = db.query(Mix).get(mix_id)
    if not mix:
        raise HTTPException(404, "Mix not found")
    return mix


@app.post("/mixes/{mix_id}/favorite")
def toggle_favorite(
    mix_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    fav = (
        db.query(Favorite)
        .filter_by(user_id=user.id, mix_id=mix_id)
        .first()
    )

    if fav:
        db.delete(fav)
        db.commit()
        return {"status": "removed"}

    db.add(Favorite(user_id=user.id, mix_id=mix_id))
    db.commit()
    return {"status": "added"}
