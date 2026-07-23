from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from bot.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
