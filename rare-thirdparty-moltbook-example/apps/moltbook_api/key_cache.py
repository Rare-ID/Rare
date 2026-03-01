from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from rare_identity_verifier import parse_rare_jwks


@dataclass
class RareKeyCache:
    initial_jwks: dict
    refresh_fn: Callable[[], dict] | None = None
    key_cache: dict[str, Ed25519PublicKey] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.key_cache = parse_rare_jwks(self.initial_jwks)

    def resolve(self, kid: str) -> Ed25519PublicKey | None:
        key = self.key_cache.get(kid)
        if key is not None:
            return key

        if self.refresh_fn is None:
            return None

        refreshed = parse_rare_jwks(self.refresh_fn())
        self.key_cache.update(refreshed)
        return self.key_cache.get(kid)
