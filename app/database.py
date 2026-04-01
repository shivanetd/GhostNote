from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
import logging

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient = None


async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_url)
    db = _client[settings.db_name]
    # MongoDB native TTL index: auto-deletes documents when expires_at <= now
    # expireAfterSeconds=0 means the field value IS the absolute expiry timestamp
    await db.secrets.create_index(
        "expires_at",
        expireAfterSeconds=0,
        name="ttl_expires_at",
    )
    logger.info("MongoDB connected — TTL index on secrets.expires_at ensured")


async def close_db() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB disconnected")


def get_db() -> AsyncIOMotorDatabase:
    return _client[settings.db_name]
