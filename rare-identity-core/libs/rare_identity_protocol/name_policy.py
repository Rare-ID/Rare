from __future__ import annotations

import re
import unicodedata

from rare_identity_protocol.errors import TokenValidationError


MAX_NAME_LENGTH = 48
MIN_NAME_LENGTH = 1
RESERVED_NAMES = {
    "admin",
    "root",
    "support",
    "official",
    "rare",
}
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1F\x7F]")


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKC", name.strip())


def validate_name(name: str, reserved_words: set[str] | None = None) -> str:
    normalized = normalize_name(name)
    if len(normalized) < MIN_NAME_LENGTH or len(normalized) > MAX_NAME_LENGTH:
        raise TokenValidationError("name length must be between 1 and 48")

    if _CONTROL_CHAR_RE.search(normalized):
        raise TokenValidationError("name must not include control characters")

    for char in normalized:
        if unicodedata.category(char).startswith("C"):
            raise TokenValidationError("name must not include control characters")

    deny_words = reserved_words or RESERVED_NAMES
    if normalized.casefold() in {w.casefold() for w in deny_words}:
        raise TokenValidationError("name is reserved")

    return normalized
