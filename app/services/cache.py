import hashlib
import json
from typing import Any, Optional

import redis.asyncio as redis
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CacheService:
    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        if self._redis is None:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("redis_connected url=%s", settings.redis_url)

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None

    @property
    def client(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("Redis not connected")
        return self._redis

    @staticmethod
    def text_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _key(self, text_hash: str, rules: Optional[list] = None) -> str:
        rules_part = ",".join(sorted(rules)) if rules else "all"
        return f"anon:{text_hash}:{rules_part}"

    async def get(self, text: str, rules: Optional[list] = None) -> Optional[dict]:
        try:
            key = self._key(self.text_hash(text), rules)
            data = await self.client.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning("cache_get_error: %s", e)
        return None

    async def set(self, text: str, result: dict, rules: Optional[list] = None, ttl: Optional[int] = None) -> None:
        try:
            key = self._key(self.text_hash(text), rules)
            await self.client.set(
                key,
                json.dumps(result, ensure_ascii=False),
                ex=ttl or settings.cache_ttl,
            )
        except Exception as e:
            logger.warning("cache_set_error: %s", e)

    async def ping(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False


cache_service = CacheService()
