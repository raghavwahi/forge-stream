import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: datetime
    iat: datetime
    jti: str
    family_id: str | None = None


class JWTManager:
    def __init__(
        self,
        secret_key: str,
        algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
    ) -> None:
        self._secret = secret_key
        self._algorithm = algorithm
        self._access_expire = timedelta(minutes=access_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_expire_days)

    def create_access_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "type": "access",
            "exp": now + self._access_expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(
        self, user_id: str, family_id: str | None = None
    ) -> tuple[str, str, datetime]:
        now = datetime.now(timezone.utc)
        fid = family_id or str(uuid.uuid4())
        expires_at = now + self._refresh_expire
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expires_at,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "family_id": fid,
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return token, fid, expires_at

    def decode_token(self, token: str) -> TokenPayload:
        try:
            data = jwt.decode(
                token, self._secret, algorithms=[self._algorithm]
            )
            return TokenPayload(**data)
        except JWTError:
            raise
