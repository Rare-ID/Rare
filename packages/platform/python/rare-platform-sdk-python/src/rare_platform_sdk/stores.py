from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from rare_identity_protocol import now_ts

from rare_platform_sdk.types import AuthChallenge, PlatformSession


def _ttl_seconds(expires_at: int) -> int:
    return max(1, expires_at - now_ts())


class InMemoryChallengeStore:
    def __init__(self) -> None:
        self._challenges: dict[str, AuthChallenge] = {}

    async def set(self, challenge: AuthChallenge) -> None:
        self._challenges[challenge.nonce] = challenge

    async def consume(self, nonce: str) -> AuthChallenge | None:
        return self._challenges.pop(nonce, None)


class InMemoryReplayStore:
    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    async def claim(self, key: str, expires_at: int) -> bool:
        self._cleanup()
        if key in self._seen:
            return False
        self._seen[key] = expires_at
        self._cleanup()
        return True

    def _cleanup(self) -> None:
        now = now_ts()
        expired = [key for key, expires_at in self._seen.items() if expires_at < now]
        for key in expired:
            self._seen.pop(key, None)


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, PlatformSession] = {}

    async def save(self, session: PlatformSession) -> None:
        self._sessions[session.session_token] = session

    async def get(self, session_token: str) -> PlatformSession | None:
        session = self._sessions.get(session_token)
        if session is None:
            return None
        if session.expires_at < now_ts():
            self._sessions.pop(session_token, None)
            return None
        return session


class RedisChallengeStore:
    def __init__(self, redis: Any, prefix: str = "rare:challenge") -> None:
        self.redis = redis
        self.prefix = prefix

    async def set(self, challenge: AuthChallenge) -> None:
        await self.redis.set(
            f"{self.prefix}:{challenge.nonce}",
            json.dumps(asdict(challenge)),
            ex=_ttl_seconds(challenge.expires_at),
        )

    async def consume(self, nonce: str) -> AuthChallenge | None:
        key = f"{self.prefix}:{nonce}"
        getdel = getattr(self.redis, "getdel", None)
        if callable(getdel):
            payload = await getdel(key)
            return None if payload is None else AuthChallenge(**json.loads(payload))

        eval_fn = getattr(self.redis, "eval", None)
        if not callable(eval_fn):
            raise RuntimeError("redis client must support getdel or eval for atomic consume")
        payload = await eval_fn(
            "local payload = redis.call('GET', KEYS[1]); if payload then redis.call('DEL', KEYS[1]); end; return payload",
            1,
            key,
        )
        return None if payload is None else AuthChallenge(**json.loads(payload))


class RedisReplayStore:
    def __init__(self, redis: Any, prefix: str = "rare:replay") -> None:
        self.redis = redis
        self.prefix = prefix

    async def claim(self, key: str, expires_at: int) -> bool:
        result = await self.redis.set(
            f"{self.prefix}:{key}",
            "1",
            ex=_ttl_seconds(expires_at),
            nx=True,
        )
        return bool(result)


class RedisSessionStore:
    def __init__(self, redis: Any, prefix: str = "rare:session") -> None:
        self.redis = redis
        self.prefix = prefix

    async def save(self, session: PlatformSession) -> None:
        await self.redis.set(
            f"{self.prefix}:{session.session_token}",
            json.dumps(asdict(session)),
            ex=_ttl_seconds(session.expires_at),
        )

    async def get(self, session_token: str) -> PlatformSession | None:
        payload = await self.redis.get(f"{self.prefix}:{session_token}")
        if payload is None:
            return None
        session = PlatformSession(**json.loads(payload))
        if session.expires_at < now_ts():
            delete = getattr(self.redis, "delete", None)
            if callable(delete):
                await delete(f"{self.prefix}:{session_token}")
            return None
        return session
