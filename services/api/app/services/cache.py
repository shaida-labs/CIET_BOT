import hashlib
import asyncio

from redis.asyncio import Redis

from app.core.config import Settings
from app.schemas import RetrievalResult


VERSION_KEY = "ciet:knowledge:version"


def _client(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )


async def _close(redis: Redis) -> None:
    try:
        await asyncio.wait_for(redis.aclose(), timeout=0.1)
    except Exception:
        pass


async def get_cached_answer(settings: Settings, query: str, language: str) -> RetrievalResult | None:
    redis = _client(settings)
    try:
        async with asyncio.timeout(0.35):
            version = await redis.get(VERSION_KEY) or "0"
            digest = hashlib.sha256(f"{language}:{query.casefold().strip()}".encode()).hexdigest()
            value = await redis.get(f"ciet:answer:{version}:{digest}")
            return RetrievalResult.model_validate_json(value) if value else None
    except Exception:
        return None
    finally:
        await _close(redis)


async def cache_answer(settings: Settings, query: str, language: str, result: RetrievalResult) -> None:
    redis = _client(settings)
    try:
        async with asyncio.timeout(0.35):
            version = await redis.get(VERSION_KEY) or "0"
            digest = hashlib.sha256(f"{language}:{query.casefold().strip()}".encode()).hexdigest()
            await redis.setex(
                f"ciet:answer:{version}:{digest}",
                settings.response_cache_seconds,
                result.model_dump_json(),
            )
    except Exception:
        pass
    finally:
        await _close(redis)


async def invalidate_knowledge_cache(settings: Settings) -> None:
    redis = _client(settings)
    try:
        async with asyncio.timeout(0.35):
            await redis.incr(VERSION_KEY)
    except Exception:
        pass
    finally:
        await _close(redis)
