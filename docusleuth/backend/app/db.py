from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
import asyncpg
from .settings import get_settings


class Database:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    @property
    def configured(self) -> bool:
        return bool(get_settings().database_url)

    async def connect(self) -> None:
        settings = get_settings()
        if not settings.database_url:
            return
        dsn = settings.database_url.replace('postgresql+asyncpg://', 'postgresql://')
        ssl = 'require' if 'sslmode=require' in dsn else None
        dsn = dsn.replace('?sslmode=require', '').replace('&sslmode=require', '')
        self.pool = await asyncpg.create_pool(
            dsn=dsn, min_size=1, max_size=8, ssl=ssl, command_timeout=45
        )
        await self.ensure_schema()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def ensure_schema(self) -> None:
        if not self.pool:
            return
        migration_dir = Path(__file__).resolve().parents[1] / 'migrations'
        async with self.pool.acquire() as conn:
            for sql_path in sorted(migration_dir.glob('*.sql')):
                await conn.execute(sql_path.read_text())

    def require_pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError(
                'Database is not configured. Provide DATABASE_URL through protected configuration.'
            )
        return self.pool

    async def execute(self, query: str, *args):
        async with self.require_pool().acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        async with self.require_pool().acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        async with self.require_pool().acquire() as conn:
            return await conn.fetchrow(query, *args)

    @asynccontextmanager
    async def transaction(self):
        async with self.require_pool().acquire() as conn:
            async with conn.transaction():
                yield conn


db = Database()
