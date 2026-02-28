from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def create(
        self,
        email: str,
        name: str,
        password_hash: str,
        provider: str = "email",
    ) -> dict:
        return await self._db.fetch_one(
            """INSERT INTO users (email, name, password_hash, provider)
               VALUES ($1, $2, $3, $4)
               RETURNING id, email, name, avatar_url, password_hash,
                         provider, is_active, is_verified,
                         created_at, updated_at""",
            email,
            name,
            password_hash,
            provider,
        )

    async def create_oauth_user(
        self, email: str, name: str, provider: str, avatar_url: str | None
    ) -> dict:
        return await self._db.fetch_one(
            """INSERT INTO users (email, name, provider, avatar_url, is_verified)
               VALUES ($1, $2, $3, $4, true)
               RETURNING id, email, name, avatar_url, password_hash,
                         provider, is_active, is_verified,
                         created_at, updated_at""",
            email,
            name,
            provider,
            avatar_url,
        )

    async def find_by_email(self, email: str) -> dict | None:
        return await self._db.fetch_one(
            "SELECT * FROM users WHERE email = $1", email
        )

    async def find_by_id(self, user_id: str) -> dict | None:
        return await self._db.fetch_one(
            "SELECT * FROM users WHERE id = $1::uuid", user_id
        )

    async def update_password(
        self, user_id: str, password_hash: str
    ) -> None:
        await self._db.execute(
            """UPDATE users SET password_hash = $1, updated_at = NOW()
               WHERE id = $2::uuid""",
            password_hash,
            user_id,
        )

    async def mark_verified(self, user_id: str) -> None:
        await self._db.execute(
            """UPDATE users SET is_verified = true, updated_at = NOW()
               WHERE id = $1::uuid""",
            user_id,
        )
