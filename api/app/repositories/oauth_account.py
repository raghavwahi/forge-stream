from app.repositories.base import BaseRepository


class OAuthAccountRepository(BaseRepository):
    async def create(
        self,
        user_id: str,
        provider: str,
        provider_account_id: str,
        access_token: str,
    ) -> dict:
        return await self._db.fetch_one(
            """INSERT INTO oauth_accounts
                   (user_id, provider, provider_account_id, access_token)
               VALUES ($1::uuid, $2, $3, $4)
               RETURNING *""",
            user_id,
            provider,
            provider_account_id,
            access_token,
        )

    async def find_by_provider_id(
        self, provider: str, provider_account_id: str
    ) -> dict | None:
        return await self._db.fetch_one(
            """SELECT * FROM oauth_accounts
               WHERE provider = $1 AND provider_account_id = $2""",
            provider,
            provider_account_id,
        )

    async def find_by_user_and_provider(
        self, user_id: str, provider: str
    ) -> dict | None:
        return await self._db.fetch_one(
            """SELECT * FROM oauth_accounts
               WHERE user_id = $1::uuid AND provider = $2""",
            user_id,
            provider,
        )
