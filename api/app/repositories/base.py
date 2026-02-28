from app.providers.base import BaseDatabaseProvider


class BaseRepository:
    def __init__(self, db: BaseDatabaseProvider) -> None:
        self._db = db
