# DEPRECATED: SQLAlchemy data access replaced by Cosmos DB repositories in app.repositories.
# Kept temporarily for migration script (backend/scripts/migrate_to_cosmos.py).

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.ENVIRONMENT == "development")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
