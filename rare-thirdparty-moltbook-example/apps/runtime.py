from __future__ import annotations

from rare_api.main import create_app as create_rare_app
from rare_api.service import RareService

from moltbook_api.key_cache import RareKeyCache
from moltbook_api.main import create_app as create_platform_app
from moltbook_api.service import MoltbookService


def create_runtime(
    *,
    aud: str = "platform",
    challenge_ttl_seconds: int = 120,
) -> tuple[RareService, MoltbookService, object, object]:
    rare_service = RareService()

    key_cache = RareKeyCache(
        initial_jwks=rare_service.get_jwks(),
        refresh_fn=rare_service.get_jwks,
    )

    platform_service = MoltbookService(
        aud=aud,
        identity_key_resolver=key_cache.resolve,
        rare_signer_public_key_provider=rare_service.get_rare_signer_public_key,
        challenge_ttl_seconds=challenge_ttl_seconds,
    )
    rare_app = create_rare_app(rare_service)
    platform_app = create_platform_app(platform_service)
    return rare_service, platform_service, rare_app, platform_app
