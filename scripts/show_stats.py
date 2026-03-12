#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


DEFAULT_BASE_URL = "https://api.rareid.cc"
DEFAULT_SECRET_NAME = "rare-core-api-prod-admin-token"
DEFAULT_PROJECT_ID = "rare-489504"
DEFAULT_RESOLVE_IP = "136.110.131.55"
LEVELS = ("L0", "L1", "L2")


def _resolve_timezone(name: str | None) -> ZoneInfo:
    if name:
        return ZoneInfo(name)
    env_name = os.getenv("TZ")
    if env_name:
        return ZoneInfo(env_name)
    local_tz = datetime.now().astimezone().tzinfo
    if isinstance(local_tz, ZoneInfo):
        return local_tz
    return ZoneInfo("UTC")


def _load_token(secret_name: str, project_id: str) -> str:
    env_token = os.getenv("RARE_ADMIN_TOKEN")
    if env_token:
        return env_token.strip()
    command = [
        "gcloud",
        "secrets",
        "versions",
        "access",
        "latest",
        "--project",
        project_id,
        "--secret",
        secret_name,
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("gcloud not found and RARE_ADMIN_TOKEN is unset") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip() or "unknown error"
        raise RuntimeError(f"failed to load admin token from Secret Manager: {stderr}") from exc
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("admin token resolved to an empty value")
    return token


def _fetch_json(base_url: str, path: str, token: str) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "rare-show-stats/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{path} returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        if _should_retry_with_resolve(base_url, exc):
            return _fetch_json_with_curl_resolve(base_url, path, token)
        raise RuntimeError(f"request to {url} failed: {exc.reason}") from exc
    except ssl.SSLError as exc:
        if _should_retry_with_resolve(base_url, exc):
            return _fetch_json_with_curl_resolve(base_url, path, token)
        raise RuntimeError(f"request to {url} failed: {exc}") from exc


def _should_retry_with_resolve(base_url: str, exc: BaseException) -> bool:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname != "api.rareid.cc":
        return False
    detail = str(getattr(exc, "reason", exc))
    return "UNEXPECTED_EOF_WHILE_READING" in detail or "EOF occurred in violation of protocol" in detail


def _fetch_json_with_curl_resolve(base_url: str, path: str, token: str) -> Any:
    parsed = urlparse(base_url)
    host = parsed.hostname
    if host is None:
        raise RuntimeError(f"cannot determine host from {base_url}")
    port = parsed.port or 443
    resolve_ip = os.getenv("RARE_API_RESOLVE_IP", DEFAULT_RESOLVE_IP).strip()
    url = f"{base_url.rstrip('/')}{path}"
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--fail",
        "--resolve",
        f"{host}:{port}:{resolve_ip}",
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Accept: application/json",
        "-H",
        "User-Agent: rare-show-stats/1.0",
        url,
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("curl not found for SSL fallback path") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() or exc.stdout.strip() or "unknown error"
        raise RuntimeError(f"curl fallback failed for {path}: {stderr}") from exc
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"curl fallback returned invalid JSON for {path}") from exc


def _relative_time(ts: int | None, *, now_ts: int) -> str:
    if ts is None:
        return "-"
    delta = ts - now_ts
    suffix = "from now" if delta >= 0 else "ago"
    seconds = abs(delta)
    if seconds < 60:
        amount = seconds
        unit = "second"
    elif seconds < 3600:
        amount = seconds // 60
        unit = "minute"
    elif seconds < 86400:
        amount = seconds // 3600
        unit = "hour"
    else:
        amount = seconds // 86400
        unit = "day"
    plural = "" if amount == 1 else "s"
    return f"{amount} {unit}{plural} {suffix}"


def _format_offset(dt: datetime) -> str:
    offset = dt.utcoffset()
    if offset is None:
        return "UTC"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def _format_human_time(ts: int | None, *, tz: ZoneInfo, now_ts: int) -> str:
    if ts is None:
        return "-"
    dt = datetime.fromtimestamp(ts, tz)
    display = dt.strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")
    return f"{display} {_format_offset(dt)} ({_relative_time(ts, now_ts=now_ts)})"


def _aggregate_stats(agents: list[dict[str, Any]], platforms: list[dict[str, Any]], *, tz: ZoneInfo) -> dict[str, Any]:
    now = datetime.now(tz)
    now_ts = int(now.timestamp())
    level_counts = Counter(str(agent.get("level", "L0")) for agent in agents)
    latest_agent_ts = max((int(agent["created_at"]) for agent in agents if agent.get("created_at") is not None), default=None)
    latest_platform_ts = max(
        (int(platform["created_at"]) for platform in platforms if platform.get("created_at") is not None),
        default=None,
    )
    return {
        "agents": {
            "total_registered": len(agents),
            "active": sum(1 for agent in agents if agent.get("status") == "active"),
            "by_level": {level: level_counts.get(level, 0) for level in LEVELS},
            "latest_registered_at": latest_agent_ts,
            "latest_registered_at_human": _format_human_time(latest_agent_ts, tz=tz, now_ts=now_ts),
        },
        "platforms": {
            "total_registered": len(platforms),
            "active": sum(1 for platform in platforms if platform.get("status") == "active"),
            "latest_registered_at": latest_platform_ts,
            "latest_registered_at_human": _format_human_time(latest_platform_ts, tz=tz, now_ts=now_ts),
        },
        "updated_at": now_ts,
        "updated_at_human": _format_human_time(now_ts, tz=tz, now_ts=now_ts),
        "timezone": getattr(tz, "key", str(tz)),
    }


def _print_report(stats: dict[str, Any], *, base_url: str) -> None:
    print("Rare Stats")
    print(f"API: {base_url}")
    print(f"Updated: {stats['updated_at_human']}")
    print("")
    print(f"Agents: {stats['agents']['total_registered']} total, {stats['agents']['active']} active")
    print(
        "Levels: "
        f"L0={stats['agents']['by_level']['L0']}  "
        f"L1={stats['agents']['by_level']['L1']}  "
        f"L2={stats['agents']['by_level']['L2']}"
    )
    print(f"Latest agent registration: {stats['agents']['latest_registered_at_human']}")
    print("")
    print(f"Platforms: {stats['platforms']['total_registered']} total, {stats['platforms']['active']} active")
    print(f"Latest platform registration: {stats['platforms']['latest_registered_at_human']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show Rare agent/platform stats using existing admin APIs")
    parser.add_argument("--base-url", default=os.getenv("RARE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--project", default=os.getenv("RARE_GCP_PROJECT_ID", DEFAULT_PROJECT_ID))
    parser.add_argument("--secret", default=os.getenv("RARE_ADMIN_TOKEN_SECRET", DEFAULT_SECRET_NAME))
    parser.add_argument("--timezone", default=None, help="IANA timezone, for example Asia/Shanghai or America/Los_Angeles")
    parser.add_argument("--json", action="store_true", help="Print aggregated stats as JSON")
    args = parser.parse_args()

    try:
        tz = _resolve_timezone(args.timezone)
        token = _load_token(secret_name=args.secret, project_id=args.project)
        agents = _fetch_json(args.base_url, "/v1/admin/agents", token)
        platforms = _fetch_json(args.base_url, "/v1/admin/platforms", token)
        stats = _aggregate_stats(agents, platforms, tz=tz)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        _print_report(stats, base_url=args.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
