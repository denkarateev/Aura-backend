import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi.security import HTTPBearer
from jose import jwt

from app.core.config import ALGORITHM, SECRET_KEY

security = HTTPBearer(auto_error=False)

# Access token lifetime.
# Юзер: «не удалось загрузить регуляров» — корень был в том что 15 мин
# истекали и iOS пока не имеет refresh-логики. Возвращаем 7 дней до
# момента когда iOS-агент подключит /auth/refresh и автоматический retry.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Refresh token lifetime: 30 days.
REFRESH_TOKEN_EXPIRE_DAYS = 30


def create_access_token(data: dict) -> str:
    """Issue a short-lived access JWT (15 min)."""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Generate a cryptographically-random refresh token.

    Returns (raw_token, token_hash, expires_at).
    - raw_token  — URL-safe base64 string, returned to the client once.
    - token_hash — SHA-256 hex, stored in DB; raw token is never persisted.
    - expires_at — UTC datetime, 30 days from now.
    """
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return raw, token_hash, expires_at


def hash_refresh_token(raw_token: str) -> str:
    """Hash a raw refresh token for DB lookup."""
    return hashlib.sha256(raw_token.encode()).hexdigest()
