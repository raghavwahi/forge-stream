from datetime import datetime

from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository):
    async def create(
        self,
        user_id: str,
        token_hash: str,
        family_id: str,
        expires_at: datetime,
    ) -> dict:
        return await self._db.fetch_one(
            """INSERT INTO refresh_tokens
                   (user_id, token_hash, family_id, expires_at)
               VALUES ($1::uuid, $2, $3::uuid, $4)
               RETURNING *""",
            user_id,
            token_hash,
            family_id,
            expires_at,
        )

    async def find_by_token_hash(self, token_hash: str) -> dict | None:
        return await self._db.fetch_one(
            """SELECT * FROM refresh_tokens
               WHERE token_hash = $1
                 AND revoked_at IS NULL
                 AND expires_at > NOW()""",
            token_hash,
        )

    async def revoke(self, token_id: str) -> None:
        await self._db.execute(
            "UPDATE refresh_tokens SET revoked_at = NOW() WHERE id = $1::uuid",
            token_id,
        )

    async def revoke_family(self, family_id: str) -> None:
        await self._db.execute(
            """UPDATE refresh_tokens SET revoked_at = NOW()
               WHERE family_id = $1::uuid AND revoked_at IS NULL""",
            family_id,
        )

    async def revoke_all_for_user(self, user_id: str) -> None:
        await self._db.execute(
            """UPDATE refresh_tokens SET revoked_at = NOW()
               WHERE user_id = $1::uuid AND revoked_at IS NULL""",
            user_id,
        )
