from datetime import datetime

from app.repositories.base import BaseRepository


class PasswordResetRepository(BaseRepository):
    async def create(
        self, user_id: str, token_hash: str, expires_at: datetime
    ) -> dict:
        return await self._db.fetch_one(
            """INSERT INTO password_reset_tokens
                   (user_id, token_hash, expires_at)
               VALUES ($1::uuid, $2, $3)
               RETURNING *""",
            user_id,
            token_hash,
            expires_at,
        )

    async def find_valid_by_hash(self, token_hash: str) -> dict | None:
        return await self._db.fetch_one(
            """SELECT * FROM password_reset_tokens
               WHERE token_hash = $1
                 AND used_at IS NULL
                 AND expires_at > NOW()""",
            token_hash,
        )

    async def mark_used(self, token_id: str) -> None:
        await self._db.execute(
            """UPDATE password_reset_tokens SET used_at = NOW()
               WHERE id = $1::uuid""",
            token_id,
        )

    async def revoke_all_for_user(self, user_id: str) -> None:
        await self._db.execute(
            """UPDATE password_reset_tokens SET used_at = NOW()
               WHERE user_id = $1::uuid AND used_at IS NULL""",
            user_id,
        )
