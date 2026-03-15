from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI


REPO_ROOT = Path(__file__).resolve().parents[1]
RARE_SERVICES_DIR = REPO_ROOT / "services" / "rare-identity-core" / "services"
PLATFORM_STUB_DIR = REPO_ROOT / "packages" / "python" / "rare-agent-sdk-python" / "tests"
RUNTIME_DIR = REPO_ROOT / ".tmp-run" / "local-stack"

for candidate in (RARE_SERVICES_DIR, PLATFORM_STUB_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)


def _set_default_env() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("RARE_ENV", "dev")
    os.environ.setdefault("RARE_STORAGE_BACKEND", "sqlite")
    os.environ.setdefault("RARE_SQLITE_STATE_FILE", str(RUNTIME_DIR / "rare-dev.sqlite3"))
    os.environ.setdefault("RARE_KEY_PROVIDER", "file")
    os.environ.setdefault("RARE_KEYRING_FILE", str(RUNTIME_DIR / "rare-keyring.json"))
    os.environ.setdefault("RARE_EMAIL_PROVIDER", "noop")
    os.environ.setdefault("RARE_DNS_RESOLVER", "noop")
    os.environ.setdefault("RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS", "true")
    os.environ.setdefault("RARE_LOCAL_DNS_SHORTCUT", "true")


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def build_stack_app(*, platform_aud: str) -> FastAPI:
    _set_default_env()
    from _platform_stub import PlatformStubService, create_platform_app
    from rare_api.main import create_app
    from rare_api.key_provider import FileKeyProvider
    from rare_api.service import RareService
    from rare_api.state_store import SqliteStateStore

    rare_service_ref: RareService | None = None

    def _local_dns_txt_resolver(name: str) -> list[str]:
        service = rare_service_ref
        if service is None:
            return []
        now = int(time.time())
        values: list[str] = []
        for challenge in service.platform_register_challenges.values():
            if getattr(challenge, "status", "") != "issued":
                continue
            if getattr(challenge, "expires_at", 0) < now - 30:
                continue
            if getattr(challenge, "txt_name", "") == name:
                txt_value = getattr(challenge, "txt_value", "")
                if txt_value:
                    values.append(txt_value)
        return values

    dns_resolver = _local_dns_txt_resolver if _env_bool("RARE_LOCAL_DNS_SHORTCUT", default=True) else None

    rare_service = RareService(
        allow_local_upgrade_shortcuts=True,
        dns_txt_resolver=dns_resolver,
        state_store=SqliteStateStore(path=os.environ["RARE_SQLITE_STATE_FILE"]),
        key_provider=FileKeyProvider(path=os.environ["RARE_KEYRING_FILE"]),
    )
    rare_service_ref = rare_service
    platform_service = PlatformStubService(
        aud=platform_aud,
        identity_key_resolver=lambda kid: rare_service.get_identity_public_key(kid),
        rare_signer_public_key_provider=rare_service.get_rare_signer_public_key,
    )

    app = FastAPI(title="Rare Local Integration Stack", version="0.1.0")
    app.mount("/platform", create_platform_app(platform_service))
    app.mount("/", create_app(rare_service))
    return app


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local Rare + Platform stub integration stack")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--platform-aud", default="platform")
    parser.add_argument("--log-level", default="info", choices=["critical", "error", "warning", "info", "debug", "trace"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    app = build_stack_app(platform_aud=args.platform_aud)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
