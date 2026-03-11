from __future__ import annotations

import json
import pickle
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

from rare_identity_protocol import ExpiringMap, ExpiringSet


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _project_snapshot_to_sqlite(connection: sqlite3.Connection, snapshot: dict[str, Any]) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS rare_agents (
            agent_id TEXT PRIMARY KEY,
            key_mode TEXT NOT NULL,
            name TEXT NOT NULL,
            level TEXT NOT NULL,
            owner_id TEXT,
            org_id TEXT,
            social_accounts_jsonb TEXT NOT NULL,
            twitter_jsonb TEXT,
            github_jsonb TEXT,
            linkedin_jsonb TEXT,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            name_updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rare_identity_profiles (
            agent_id TEXT PRIMARY KEY,
            risk_score REAL NOT NULL,
            labels_jsonb TEXT NOT NULL,
            summary TEXT NOT NULL,
            metadata_jsonb TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            version INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rare_hosted_agent_keys (
            agent_id TEXT PRIMARY KEY,
            public_key_b64 TEXT NOT NULL,
            private_key_ciphertext TEXT NOT NULL,
            kms_key_name TEXT,
            kms_key_version TEXT,
            created_at INTEGER,
            rotated_at INTEGER,
            status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rare_hosted_management_tokens (
            agent_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL,
            issued_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            revoked_at INTEGER,
            version INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rare_platforms (
            platform_id TEXT PRIMARY KEY,
            platform_aud TEXT NOT NULL UNIQUE,
            domain TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rare_platform_keys (
            kid TEXT PRIMARY KEY,
            platform_id TEXT NOT NULL,
            public_key_b64 TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rare_platform_negative_events (
            platform_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            platform_aud TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            category TEXT NOT NULL,
            severity INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            occurred_at INTEGER NOT NULL,
            evidence_hash TEXT,
            ingested_at INTEGER NOT NULL,
            PRIMARY KEY (platform_id, event_id)
        );
        CREATE TABLE IF NOT EXISTS rare_upgrade_requests (
            upgrade_request_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            target_level TEXT NOT NULL,
            status TEXT NOT NULL,
            requested_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            contact_email_hash TEXT,
            contact_email_masked TEXT,
            email_verified_at INTEGER,
            social_provider TEXT,
            social_account_jsonb TEXT,
            social_verified_at INTEGER,
            failure_reason TEXT,
            last_transition_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rare_audit_events (
            event_id TEXT PRIMARY KEY,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            agent_id TEXT,
            event_type TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            status TEXT NOT NULL,
            request_id TEXT,
            metadata_jsonb TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        """
    )

    for table in (
        "rare_agents",
        "rare_identity_profiles",
        "rare_hosted_agent_keys",
        "rare_hosted_management_tokens",
        "rare_platforms",
        "rare_platform_keys",
        "rare_platform_negative_events",
        "rare_upgrade_requests",
        "rare_audit_events",
    ):
        connection.execute(f"DELETE FROM {table}")

    for agent_id, record in snapshot.get("agents", {}).items():
        connection.execute(
            """
            INSERT INTO rare_agents (
                agent_id, key_mode, name, level, owner_id, org_id, social_accounts_jsonb,
                twitter_jsonb, github_jsonb, linkedin_jsonb, status, created_at, name_updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                record.get("key_mode", "hosted-signer"),
                record["name"],
                record.get("level", "L0"),
                record.get("owner_id"),
                record.get("org_id"),
                _json_text(record.get("social_accounts", {})),
                _json_text(record.get("twitter")) if record.get("twitter") is not None else None,
                _json_text(record.get("github")) if record.get("github") is not None else None,
                _json_text(record.get("linkedin")) if record.get("linkedin") is not None else None,
                record.get("status", "active"),
                int(record["created_at"]),
                int(record["name_updated_at"]),
            ),
        )

    for agent_id, record in snapshot.get("identity_profiles", {}).items():
        connection.execute(
            """
            INSERT INTO rare_identity_profiles (
                agent_id, risk_score, labels_jsonb, summary, metadata_jsonb, updated_at, version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                float(record.get("risk_score", 0.0)),
                _json_text(record.get("labels", [])),
                record.get("summary", ""),
                _json_text(record.get("metadata", {})),
                int(record["updated_at"]),
                int(record["version"]),
            ),
        )

    agents = snapshot.get("agents", {})
    hosted_keys = snapshot.get("hosted_agent_private_keys", {})
    for agent_id, ciphertext in hosted_keys.items():
        agent = agents.get(agent_id, {})
        connection.execute(
            """
            INSERT INTO rare_hosted_agent_keys (
                agent_id, public_key_b64, private_key_ciphertext, kms_key_name, kms_key_version,
                created_at, rotated_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                agent_id,
                ciphertext,
                None,
                None,
                int(agent.get("created_at", 0)),
                None,
                "active",
            ),
        )

    for agent_id, record in snapshot.get("hosted_management_tokens", {}).items():
        connection.execute(
            """
            INSERT INTO rare_hosted_management_tokens (
                agent_id, token_hash, issued_at, expires_at, revoked_at, version
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                record["token_hash"],
                int(record["issued_at"]),
                int(record["expires_at"]),
                record.get("revoked_at"),
                int(record.get("version", 1)),
            ),
        )

    for platform_aud, record in snapshot.get("platforms", {}).items():
        connection.execute(
            """
            INSERT INTO rare_platforms (
                platform_id, platform_aud, domain, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record["platform_id"],
                platform_aud,
                record["domain"],
                record.get("status", "active"),
                int(record["created_at"]),
                int(record["updated_at"]),
            ),
        )
        for key in record.get("keys", {}).values():
            connection.execute(
                """
                INSERT INTO rare_platform_keys (kid, platform_id, public_key_b64, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    key["kid"],
                    record["platform_id"],
                    key["public_key_b64"],
                    key.get("status", "active"),
                    int(key["created_at"]),
                ),
            )

    for event in snapshot.get("platform_events", {}).values():
        connection.execute(
            """
            INSERT INTO rare_platform_negative_events (
                platform_id, event_id, platform_aud, agent_id, category, severity,
                outcome, occurred_at, evidence_hash, ingested_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["platform_id"],
                event["event_id"],
                event["platform_aud"],
                event["agent_id"],
                event["category"],
                int(event["severity"]),
                event["outcome"],
                int(event["occurred_at"]),
                event.get("evidence_hash"),
                int(event["ingested_at"]),
            ),
        )

    for request_id, record in snapshot.get("upgrade_requests", {}).items():
        connection.execute(
            """
            INSERT INTO rare_upgrade_requests (
                upgrade_request_id, agent_id, target_level, status, requested_at, expires_at,
                contact_email_hash, contact_email_masked, email_verified_at, social_provider,
                social_account_jsonb, social_verified_at, failure_reason, last_transition_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                record["agent_id"],
                record["target_level"],
                record["status"],
                int(record["requested_at"]),
                int(record["expires_at"]),
                record.get("contact_email_hash"),
                record.get("contact_email_masked"),
                record.get("email_verified_at"),
                record.get("social_provider"),
                _json_text(record.get("social_account")) if record.get("social_account") is not None else None,
                record.get("social_verified_at"),
                record.get("failure_reason"),
                int(record["last_transition_at"]),
            ),
        )

    for event in snapshot.get("audit_events", []):
        connection.execute(
            """
            INSERT INTO rare_audit_events (
                event_id, actor_type, actor_id, agent_id, event_type, resource_type,
                resource_id, status, request_id, metadata_jsonb, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["actor_type"],
                event.get("actor_id"),
                event.get("agent_id"),
                event["event_type"],
                event["resource_type"],
                event["resource_id"],
                event["status"],
                event.get("request_id"),
                _json_text(event.get("metadata", {})),
                int(event["created_at"]),
            ),
        )


def _project_snapshot_to_postgres(connection: Any, namespace: str, snapshot: dict[str, Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rare_agents (
                namespace TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                key_mode TEXT NOT NULL,
                name TEXT NOT NULL,
                level TEXT NOT NULL,
                owner_id TEXT,
                org_id TEXT,
                social_accounts_jsonb TEXT NOT NULL,
                twitter_jsonb TEXT,
                github_jsonb TEXT,
                linkedin_jsonb TEXT,
                status TEXT NOT NULL,
                created_at BIGINT NOT NULL,
                name_updated_at BIGINT NOT NULL,
                PRIMARY KEY (namespace, agent_id)
            );
            CREATE TABLE IF NOT EXISTS rare_identity_profiles (
                namespace TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                risk_score DOUBLE PRECISION NOT NULL,
                labels_jsonb TEXT NOT NULL,
                summary TEXT NOT NULL,
                metadata_jsonb TEXT NOT NULL,
                updated_at BIGINT NOT NULL,
                version BIGINT NOT NULL,
                PRIMARY KEY (namespace, agent_id)
            );
            CREATE TABLE IF NOT EXISTS rare_hosted_agent_keys (
                namespace TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                public_key_b64 TEXT NOT NULL,
                private_key_ciphertext TEXT NOT NULL,
                kms_key_name TEXT,
                kms_key_version TEXT,
                created_at BIGINT,
                rotated_at BIGINT,
                status TEXT NOT NULL,
                PRIMARY KEY (namespace, agent_id)
            );
            CREATE TABLE IF NOT EXISTS rare_hosted_management_tokens (
                namespace TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                issued_at BIGINT NOT NULL,
                expires_at BIGINT NOT NULL,
                revoked_at BIGINT,
                version BIGINT NOT NULL,
                PRIMARY KEY (namespace, agent_id)
            );
            CREATE TABLE IF NOT EXISTS rare_platforms (
                namespace TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                platform_aud TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL,
                PRIMARY KEY (namespace, platform_id),
                UNIQUE (namespace, platform_aud)
            );
            CREATE TABLE IF NOT EXISTS rare_platform_keys (
                namespace TEXT NOT NULL,
                kid TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                public_key_b64 TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at BIGINT NOT NULL,
                PRIMARY KEY (namespace, kid)
            );
            CREATE TABLE IF NOT EXISTS rare_platform_negative_events (
                namespace TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                platform_aud TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                category TEXT NOT NULL,
                severity INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                occurred_at BIGINT NOT NULL,
                evidence_hash TEXT,
                ingested_at BIGINT NOT NULL,
                PRIMARY KEY (namespace, platform_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS rare_upgrade_requests (
                namespace TEXT NOT NULL,
                upgrade_request_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                target_level TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_at BIGINT NOT NULL,
                expires_at BIGINT NOT NULL,
                contact_email_hash TEXT,
                contact_email_masked TEXT,
                email_verified_at BIGINT,
                social_provider TEXT,
                social_account_jsonb TEXT,
                social_verified_at BIGINT,
                failure_reason TEXT,
                last_transition_at BIGINT NOT NULL,
                PRIMARY KEY (namespace, upgrade_request_id)
            );
            CREATE TABLE IF NOT EXISTS rare_audit_events (
                namespace TEXT NOT NULL,
                event_id TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                agent_id TEXT,
                event_type TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                status TEXT NOT NULL,
                request_id TEXT,
                metadata_jsonb TEXT NOT NULL,
                created_at BIGINT NOT NULL,
                PRIMARY KEY (namespace, event_id)
            );
            """
        )

        for table in (
            "rare_agents",
            "rare_identity_profiles",
            "rare_hosted_agent_keys",
            "rare_hosted_management_tokens",
            "rare_platforms",
            "rare_platform_keys",
            "rare_platform_negative_events",
            "rare_upgrade_requests",
            "rare_audit_events",
        ):
            cursor.execute(f"DELETE FROM {table} WHERE namespace = %s", (namespace,))

        for agent_id, record in snapshot.get("agents", {}).items():
            cursor.execute(
                """
                INSERT INTO rare_agents (
                    namespace, agent_id, key_mode, name, level, owner_id, org_id, social_accounts_jsonb,
                    twitter_jsonb, github_jsonb, linkedin_jsonb, status, created_at, name_updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    namespace,
                    agent_id,
                    record.get("key_mode", "hosted-signer"),
                    record["name"],
                    record.get("level", "L0"),
                    record.get("owner_id"),
                    record.get("org_id"),
                    _json_text(record.get("social_accounts", {})),
                    _json_text(record.get("twitter")) if record.get("twitter") is not None else None,
                    _json_text(record.get("github")) if record.get("github") is not None else None,
                    _json_text(record.get("linkedin")) if record.get("linkedin") is not None else None,
                    record.get("status", "active"),
                    int(record["created_at"]),
                    int(record["name_updated_at"]),
                ),
            )

        for agent_id, record in snapshot.get("identity_profiles", {}).items():
            cursor.execute(
                """
                INSERT INTO rare_identity_profiles (
                    namespace, agent_id, risk_score, labels_jsonb, summary, metadata_jsonb, updated_at, version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    namespace,
                    agent_id,
                    float(record.get("risk_score", 0.0)),
                    _json_text(record.get("labels", [])),
                    record.get("summary", ""),
                    _json_text(record.get("metadata", {})),
                    int(record["updated_at"]),
                    int(record["version"]),
                ),
            )

        agents = snapshot.get("agents", {})
        for agent_id, ciphertext in snapshot.get("hosted_agent_private_keys", {}).items():
            agent = agents.get(agent_id, {})
            cursor.execute(
                """
                INSERT INTO rare_hosted_agent_keys (
                    namespace, agent_id, public_key_b64, private_key_ciphertext, kms_key_name,
                    kms_key_version, created_at, rotated_at, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    namespace,
                    agent_id,
                    agent_id,
                    ciphertext,
                    None,
                    None,
                    int(agent.get("created_at", 0)),
                    None,
                    "active",
                ),
            )

        for agent_id, record in snapshot.get("hosted_management_tokens", {}).items():
            cursor.execute(
                """
                INSERT INTO rare_hosted_management_tokens (
                    namespace, agent_id, token_hash, issued_at, expires_at, revoked_at, version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    namespace,
                    agent_id,
                    record["token_hash"],
                    int(record["issued_at"]),
                    int(record["expires_at"]),
                    record.get("revoked_at"),
                    int(record.get("version", 1)),
                ),
            )

        for platform_aud, record in snapshot.get("platforms", {}).items():
            cursor.execute(
                """
                INSERT INTO rare_platforms (
                    namespace, platform_id, platform_aud, domain, status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    namespace,
                    record["platform_id"],
                    platform_aud,
                    record["domain"],
                    record.get("status", "active"),
                    int(record["created_at"]),
                    int(record["updated_at"]),
                ),
            )
            for key in record.get("keys", {}).values():
                cursor.execute(
                    """
                    INSERT INTO rare_platform_keys (
                        namespace, kid, platform_id, public_key_b64, status, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        namespace,
                        key["kid"],
                        record["platform_id"],
                        key["public_key_b64"],
                        key.get("status", "active"),
                        int(key["created_at"]),
                    ),
                )

        for event in snapshot.get("platform_events", {}).values():
            cursor.execute(
                """
                INSERT INTO rare_platform_negative_events (
                    namespace, platform_id, event_id, platform_aud, agent_id, category, severity,
                    outcome, occurred_at, evidence_hash, ingested_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    namespace,
                    event["platform_id"],
                    event["event_id"],
                    event["platform_aud"],
                    event["agent_id"],
                    event["category"],
                    int(event["severity"]),
                    event["outcome"],
                    int(event["occurred_at"]),
                    event.get("evidence_hash"),
                    int(event["ingested_at"]),
                ),
            )

        for request_id, record in snapshot.get("upgrade_requests", {}).items():
            cursor.execute(
                """
                INSERT INTO rare_upgrade_requests (
                    namespace, upgrade_request_id, agent_id, target_level, status, requested_at, expires_at,
                    contact_email_hash, contact_email_masked, email_verified_at, social_provider,
                    social_account_jsonb, social_verified_at, failure_reason, last_transition_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    namespace,
                    request_id,
                    record["agent_id"],
                    record["target_level"],
                    record["status"],
                    int(record["requested_at"]),
                    int(record["expires_at"]),
                    record.get("contact_email_hash"),
                    record.get("contact_email_masked"),
                    record.get("email_verified_at"),
                    record.get("social_provider"),
                    _json_text(record.get("social_account")) if record.get("social_account") is not None else None,
                    record.get("social_verified_at"),
                    record.get("failure_reason"),
                    int(record["last_transition_at"]),
                ),
            )

        for event in snapshot.get("audit_events", []):
            cursor.execute(
                """
                INSERT INTO rare_audit_events (
                    namespace, event_id, actor_type, actor_id, agent_id, event_type, resource_type,
                    resource_id, status, request_id, metadata_jsonb, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    namespace,
                    event["event_id"],
                    event["actor_type"],
                    event.get("actor_id"),
                    event.get("agent_id"),
                    event["event_type"],
                    event["resource_type"],
                    event["resource_id"],
                    event["status"],
                    event.get("request_id"),
                    _json_text(event.get("metadata", {})),
                    int(event["created_at"]),
                ),
            )


class AgentStore(Protocol):
    agents: dict[str, Any]
    hosted_agent_private_keys: dict[str, Any]
    hosted_management_tokens: dict[str, Any]
    name_change_events: dict[str, list[int]]
    identity_profiles: dict[str, Any]
    identity_subscriptions: dict[str, dict[str, Any]]
    platforms: dict[str, Any]
    platform_events: dict[tuple[str, str], Any]


class UpgradeStore(Protocol):
    upgrade_requests: dict[str, Any]
    upgrade_magic_links: ExpiringMap[str, Any]
    upgrade_oauth_states: ExpiringMap[str, Any]


class ReplayStore(Protocol):
    public_write_counters: ExpiringMap[tuple[str, str], int]
    used_name_nonces: ExpiringSet[str]
    used_action_nonces: ExpiringSet[tuple[str, str]]
    used_agent_auth_nonces: ExpiringSet[tuple[str, str]]
    used_full_issue_nonces: ExpiringSet[tuple[str, str]]
    seen_upgrade_nonces: ExpiringSet[tuple[str, str]]
    seen_platform_jtis: ExpiringSet[tuple[str, str]]


class ChallengeStore(Protocol):
    platform_register_challenges: ExpiringMap[str, Any]


class SessionStore(Protocol):
    hosted_session_keys: ExpiringMap[str, Any]


@dataclass
class InMemoryAgentStore:
    agents: dict[str, Any]
    hosted_agent_private_keys: dict[str, Any]
    hosted_management_tokens: dict[str, Any]
    name_change_events: dict[str, list[int]]
    identity_profiles: dict[str, Any]
    identity_subscriptions: dict[str, dict[str, Any]]
    platforms: dict[str, Any]
    platform_events: dict[tuple[str, str], Any]


@dataclass
class InMemoryUpgradeStore:
    upgrade_requests: dict[str, Any]
    upgrade_magic_links: ExpiringMap[str, Any]
    upgrade_oauth_states: ExpiringMap[str, Any]
    management_recovery_email_links: ExpiringMap[str, Any]
    management_recovery_oauth_states: ExpiringMap[str, Any]


@dataclass
class InMemoryReplayStore:
    public_write_counters: ExpiringMap[tuple[str, str], int]
    used_name_nonces: ExpiringSet[str]
    used_action_nonces: ExpiringSet[tuple[str, str]]
    used_agent_auth_nonces: ExpiringSet[tuple[str, str]]
    used_full_issue_nonces: ExpiringSet[tuple[str, str]]
    seen_upgrade_nonces: ExpiringSet[tuple[str, str]]
    seen_platform_jtis: ExpiringSet[tuple[str, str]]


@dataclass
class InMemoryChallengeStore:
    platform_register_challenges: ExpiringMap[str, Any]


@dataclass
class InMemorySessionStore:
    hosted_session_keys: ExpiringMap[str, Any]


@dataclass
class RareStateHandles:
    agent_store: AgentStore
    upgrade_store: UpgradeStore
    replay_store: ReplayStore
    challenge_store: ChallengeStore
    session_store: SessionStore

    # Backward-compatible flattened aliases used by RareService.
    agents: dict[str, Any]
    hosted_agent_private_keys: dict[str, Any]
    hosted_management_tokens: dict[str, Any]
    hosted_session_keys: ExpiringMap[str, Any]
    public_write_counters: ExpiringMap[tuple[str, str], int]
    name_change_events: dict[str, list[int]]
    used_name_nonces: ExpiringSet[str]
    used_action_nonces: ExpiringSet[tuple[str, str]]
    used_agent_auth_nonces: ExpiringSet[tuple[str, str]]
    used_full_issue_nonces: ExpiringSet[tuple[str, str]]
    seen_upgrade_nonces: ExpiringSet[tuple[str, str]]
    identity_profiles: dict[str, Any]
    identity_subscriptions: dict[str, dict[str, Any]]
    platforms: dict[str, Any]
    platform_register_challenges: ExpiringMap[str, Any]
    platform_events: dict[tuple[str, str], Any]
    seen_platform_jtis: ExpiringSet[tuple[str, str]]
    upgrade_requests: dict[str, Any]
    upgrade_magic_links: ExpiringMap[str, Any]
    upgrade_oauth_states: ExpiringMap[str, Any]
    management_recovery_email_links: ExpiringMap[str, Any]
    management_recovery_oauth_states: ExpiringMap[str, Any]


class StateStore(Protocol):
    def open(
        self,
        *,
        replay_cache_capacity: int,
        session_cache_capacity: int,
        challenge_cache_capacity: int,
        public_rate_counter_capacity: int,
    ) -> RareStateHandles:
        """Return handles used by RareService runtime state."""


class SnapshotCapableStateStore(Protocol):
    def load_snapshot(self) -> dict[str, Any] | None:
        """Return a previously persisted snapshot payload."""

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Persist the latest snapshot payload."""

    def snapshot_revision(self) -> int | None:
        """Return the latest persisted snapshot revision, if available."""


def _new_agent_store() -> InMemoryAgentStore:
    return InMemoryAgentStore(
        agents={},
        hosted_agent_private_keys={},
        hosted_management_tokens={},
        name_change_events={},
        identity_profiles={},
        identity_subscriptions={},
        platforms={},
        platform_events={},
    )


def _new_upgrade_store(*, challenge_cache_capacity: int) -> InMemoryUpgradeStore:
    return InMemoryUpgradeStore(
        upgrade_requests={},
        upgrade_magic_links=ExpiringMap(capacity=challenge_cache_capacity),
        upgrade_oauth_states=ExpiringMap(capacity=challenge_cache_capacity),
        management_recovery_email_links=ExpiringMap(capacity=challenge_cache_capacity),
        management_recovery_oauth_states=ExpiringMap(capacity=challenge_cache_capacity),
    )


def _new_replay_store(
    *,
    replay_cache_capacity: int,
    public_rate_counter_capacity: int,
) -> InMemoryReplayStore:
    return InMemoryReplayStore(
        public_write_counters=ExpiringMap(capacity=public_rate_counter_capacity),
        used_name_nonces=ExpiringSet(capacity=replay_cache_capacity),
        used_action_nonces=ExpiringSet(capacity=replay_cache_capacity),
        used_agent_auth_nonces=ExpiringSet(capacity=replay_cache_capacity),
        used_full_issue_nonces=ExpiringSet(capacity=replay_cache_capacity),
        seen_upgrade_nonces=ExpiringSet(capacity=replay_cache_capacity),
        seen_platform_jtis=ExpiringSet(capacity=replay_cache_capacity),
    )


def _new_challenge_store(*, challenge_cache_capacity: int) -> InMemoryChallengeStore:
    return InMemoryChallengeStore(
        platform_register_challenges=ExpiringMap(capacity=challenge_cache_capacity),
    )


def _new_session_store(*, session_cache_capacity: int) -> InMemorySessionStore:
    return InMemorySessionStore(
        hosted_session_keys=ExpiringMap(capacity=session_cache_capacity),
    )


def _compose_handles(
    *,
    agent_store: AgentStore,
    upgrade_store: UpgradeStore,
    replay_store: ReplayStore,
    challenge_store: ChallengeStore,
    session_store: SessionStore,
) -> RareStateHandles:
    return RareStateHandles(
        agent_store=agent_store,
        upgrade_store=upgrade_store,
        replay_store=replay_store,
        challenge_store=challenge_store,
        session_store=session_store,
        agents=agent_store.agents,
        hosted_agent_private_keys=agent_store.hosted_agent_private_keys,
        hosted_management_tokens=agent_store.hosted_management_tokens,
        hosted_session_keys=session_store.hosted_session_keys,
        public_write_counters=replay_store.public_write_counters,
        name_change_events=agent_store.name_change_events,
        used_name_nonces=replay_store.used_name_nonces,
        used_action_nonces=replay_store.used_action_nonces,
        used_agent_auth_nonces=replay_store.used_agent_auth_nonces,
        used_full_issue_nonces=replay_store.used_full_issue_nonces,
        seen_upgrade_nonces=replay_store.seen_upgrade_nonces,
        identity_profiles=agent_store.identity_profiles,
        identity_subscriptions=agent_store.identity_subscriptions,
        platforms=agent_store.platforms,
        platform_register_challenges=challenge_store.platform_register_challenges,
        platform_events=agent_store.platform_events,
        seen_platform_jtis=replay_store.seen_platform_jtis,
        upgrade_requests=upgrade_store.upgrade_requests,
        upgrade_magic_links=upgrade_store.upgrade_magic_links,
        upgrade_oauth_states=upgrade_store.upgrade_oauth_states,
        management_recovery_email_links=upgrade_store.management_recovery_email_links,
        management_recovery_oauth_states=upgrade_store.management_recovery_oauth_states,
    )


class InMemoryStateStore:
    def open(
        self,
        *,
        replay_cache_capacity: int,
        session_cache_capacity: int,
        challenge_cache_capacity: int,
        public_rate_counter_capacity: int,
    ) -> RareStateHandles:
        return _compose_handles(
            agent_store=_new_agent_store(),
            upgrade_store=_new_upgrade_store(challenge_cache_capacity=challenge_cache_capacity),
            replay_store=_new_replay_store(
                replay_cache_capacity=replay_cache_capacity,
                public_rate_counter_capacity=public_rate_counter_capacity,
            ),
            challenge_store=_new_challenge_store(challenge_cache_capacity=challenge_cache_capacity),
            session_store=_new_session_store(session_cache_capacity=session_cache_capacity),
        )

    def readiness(self) -> dict[str, Any]:
        return {"status": "ok", "backend": "memory"}


class PostgresStateStore:
    """
    Process-shared Postgres-like state.

    Keeps durable entities (agents/platform/upgrade records) consistent across service instances
    that use the same namespace.
    """

    _lock = Lock()
    _agent_upgrade_by_namespace: dict[str, tuple[AgentStore, UpgradeStore]] = {}

    def __init__(self, *, dsn: str | None = None) -> None:
        self.dsn = dsn

    def open(
        self,
        *,
        namespace: str,
        challenge_cache_capacity: int,
    ) -> tuple[AgentStore, UpgradeStore]:
        if not self.dsn:
            with self._lock:
                existing = self._agent_upgrade_by_namespace.get(namespace)
                if existing is not None:
                    return existing
                created = (
                    _new_agent_store(),
                    _new_upgrade_store(challenge_cache_capacity=challenge_cache_capacity),
                )
                self._agent_upgrade_by_namespace[namespace] = created
                return created
        return (
            _new_agent_store(),
            _new_upgrade_store(challenge_cache_capacity=challenge_cache_capacity),
        )

    @classmethod
    def clear_namespace(cls, namespace: str) -> None:
        with cls._lock:
            cls._agent_upgrade_by_namespace.pop(namespace, None)

    def _connect(self) -> Any:
        if not self.dsn:
            raise RuntimeError("postgres dsn is required")
        try:
            import psycopg
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("psycopg is required for PostgresStateStore") from exc
        return psycopg.connect(self.dsn)

    def _ensure_snapshot_table(self) -> None:
        if not self.dsn:
            return
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rare_state_snapshot (
                        namespace TEXT PRIMARY KEY,
                        snapshot_json TEXT NOT NULL,
                        updated_at BIGINT NOT NULL
                    )
                    """
                )
            connection.commit()

    def load_snapshot(self, *, namespace: str) -> dict[str, Any] | None:
        if not self.dsn:
            return None
        self._ensure_snapshot_table()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT snapshot_json FROM rare_state_snapshot WHERE namespace = %s",
                    (namespace,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(str(row[0]))

    def save_snapshot(self, *, namespace: str, snapshot: dict[str, Any]) -> None:
        if not self.dsn:
            return
        self._ensure_snapshot_table()
        payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO rare_state_snapshot (namespace, snapshot_json, updated_at)
                    VALUES (%s, %s, EXTRACT(EPOCH FROM NOW())::BIGINT)
                    ON CONFLICT (namespace) DO UPDATE
                    SET snapshot_json = EXCLUDED.snapshot_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (namespace, payload),
                )
                _project_snapshot_to_postgres(connection, namespace, snapshot)
            connection.commit()

    def snapshot_revision(self, *, namespace: str) -> int | None:
        if not self.dsn:
            return None
        self._ensure_snapshot_table()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT updated_at FROM rare_state_snapshot WHERE namespace = %s",
                    (namespace,),
                )
                row = cursor.fetchone()
        return int(row[0]) if row is not None else None

    def readiness(self) -> dict[str, Any]:
        if not self.dsn:
            return {"status": "ok", "backend": "memory-fallback"}
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {"status": "ok", "backend": "postgres"}


class _RedisBackedExpiringMap:
    def __init__(self, *, redis_url: str | None, prefix: str, capacity: int) -> None:
        self.redis_url = redis_url
        self.prefix = prefix
        self.capacity = capacity
        self._fallback = ExpiringMap(capacity=capacity)
        self._redis = self._build_client(redis_url)

    @staticmethod
    def _build_client(redis_url: str | None) -> Any | None:
        if not redis_url:
            return None
        try:
            import redis
        except Exception:
            return None
        return redis.Redis.from_url(redis_url, decode_responses=False)

    @staticmethod
    def _encode_key(key: Any) -> bytes:
        return json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _decode_key(key: bytes) -> Any:
        return json.loads(key.decode("utf-8"))

    @staticmethod
    def _encode_value(value: Any) -> bytes:
        return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def _decode_value(value: bytes) -> Any:
        return pickle.loads(value)

    def _redis_key(self, key: Any) -> str:
        return f"{self.prefix}:{self._encode_key(key).decode('utf-8')}"

    def _decode_scan_key(self, item: bytes | str) -> Any:
        raw = item if isinstance(item, bytes) else item.encode("utf-8")
        prefix = f"{self.prefix}:".encode("utf-8")
        if not raw.startswith(prefix):
            raise ValueError(f"unexpected redis key for prefix {self.prefix}")
        return self._decode_key(raw[len(prefix) :])

    def cleanup(self, *, now: int, grace_seconds: int = 30) -> None:
        if self._redis is None:
            self._fallback.cleanup(now=now, grace_seconds=grace_seconds)

    def set(self, *, key: Any, value: Any, expires_at: int, now: int, grace_seconds: int = 30) -> None:
        if self._redis is None:
            self._fallback.set(key=key, value=value, expires_at=expires_at, now=now, grace_seconds=grace_seconds)
            return
        ttl = max(1, expires_at - now)
        self._redis.set(self._redis_key(key), self._encode_value(value), ex=ttl)

    def get(self, key: Any) -> Any | None:
        if self._redis is None:
            return self._fallback.get(key)
        payload = self._redis.get(self._redis_key(key))
        return None if payload is None else self._decode_value(payload)

    def pop(self, key: Any) -> Any | None:
        if self._redis is None:
            return self._fallback.pop(key)
        redis_key = self._redis_key(key)
        pipe = self._redis.pipeline()
        pipe.get(redis_key)
        pipe.delete(redis_key)
        payload, _ = pipe.execute()
        return None if payload is None else self._decode_value(payload)

    def discard(self, key: Any) -> None:
        if self._redis is None:
            self._fallback.discard(key)
            return
        self._redis.delete(self._redis_key(key))

    def __contains__(self, key: Any) -> bool:
        if self._redis is None:
            return key in self._fallback
        return bool(self._redis.exists(self._redis_key(key)))

    def __len__(self) -> int:
        if self._redis is None:
            return len(self._fallback)
        return sum(1 for _ in self._redis.scan_iter(match=f"{self.prefix}:*"))

    def keys(self) -> Any:
        if self._redis is None:
            return self._fallback.keys()
        return (self._decode_scan_key(item) for item in self._redis.scan_iter(match=f"{self.prefix}:*"))

    def values(self) -> Any:
        if self._redis is None:
            return self._fallback.values()
        for item in self._redis.scan_iter(match=f"{self.prefix}:*"):
            payload = self._redis.get(item)
            if payload is not None:
                yield self._decode_value(payload)

    def items(self) -> Any:
        if self._redis is None:
            return self._fallback.items()
        for item in self._redis.scan_iter(match=f"{self.prefix}:*"):
            payload = self._redis.get(item)
            if payload is not None:
                yield self._decode_scan_key(item), self._decode_value(payload)

    def snapshot_entries(self) -> list[tuple[Any, Any, int]]:
        if self._redis is None:
            return [
                (key, entry.value, entry.expires_at)
                for key, entry in self._fallback._entries.items()  # type: ignore[attr-defined]
            ]
        now = int(time.time())
        entries: list[tuple[Any, Any, int]] = []
        for item in self._redis.scan_iter(match=f"{self.prefix}:*"):
            payload = self._redis.get(item)
            ttl = self._redis.ttl(item)
            if payload is None or ttl is None or ttl < 0:
                continue
            entries.append(
                (
                    self._decode_scan_key(item),
                    self._decode_value(payload),
                    now + int(ttl),
                )
            )
        return entries


class _RedisBackedExpiringSet:
    def __init__(self, *, redis_url: str | None, prefix: str, capacity: int) -> None:
        self._store = _RedisBackedExpiringMap(redis_url=redis_url, prefix=prefix, capacity=capacity)

    def cleanup(self, *, now: int, grace_seconds: int = 30) -> None:
        self._store.cleanup(now=now, grace_seconds=grace_seconds)

    def add(self, *, key: Any, expires_at: int, now: int, grace_seconds: int = 30) -> None:
        self._store.set(key=key, value=True, expires_at=expires_at, now=now, grace_seconds=grace_seconds)

    def contains(self, key: Any) -> bool:
        return key in self._store

    def discard(self, key: Any) -> None:
        self._store.discard(key)

    def __len__(self) -> int:
        return len(self._store)

    def snapshot_entries(self) -> list[tuple[Any, int]]:
        return [(key, expires_at) for key, _, expires_at in self._store.snapshot_entries()]


class RedisReplayStore:
    """
    Process-shared Redis-like state.

    Keeps replay/session/challenge windows consistent across service instances that use the
    same namespace.
    """

    _lock = Lock()
    _replay_by_namespace: dict[str, tuple[ReplayStore, ChallengeStore, SessionStore]] = {}

    def __init__(self, *, redis_url: str | None = None) -> None:
        self.redis_url = redis_url

    def open(
        self,
        *,
        namespace: str,
        replay_cache_capacity: int,
        session_cache_capacity: int,
        challenge_cache_capacity: int,
        public_rate_counter_capacity: int,
    ) -> tuple[ReplayStore, ChallengeStore, SessionStore]:
        if not self.redis_url:
            with self._lock:
                existing = self._replay_by_namespace.get(namespace)
                if existing is not None:
                    return existing
                created = (
                    _new_replay_store(
                        replay_cache_capacity=replay_cache_capacity,
                        public_rate_counter_capacity=public_rate_counter_capacity,
                    ),
                    _new_challenge_store(challenge_cache_capacity=challenge_cache_capacity),
                    _new_session_store(session_cache_capacity=session_cache_capacity),
                )
                self._replay_by_namespace[namespace] = created
                return created
        replay_store = InMemoryReplayStore(
            public_write_counters=_RedisBackedExpiringMap(
                redis_url=self.redis_url,
                prefix=f"rare:ratelimit:public_write:{namespace}",
                capacity=public_rate_counter_capacity,
            ),
            used_name_nonces=_RedisBackedExpiringSet(
                redis_url=self.redis_url,
                prefix=f"rare:nonce:name:{namespace}",
                capacity=replay_cache_capacity,
            ),
            used_action_nonces=_RedisBackedExpiringSet(
                redis_url=self.redis_url,
                prefix=f"rare:nonce:action:{namespace}",
                capacity=replay_cache_capacity,
            ),
            used_agent_auth_nonces=_RedisBackedExpiringSet(
                redis_url=self.redis_url,
                prefix=f"rare:nonce:agent_auth:{namespace}",
                capacity=replay_cache_capacity,
            ),
            used_full_issue_nonces=_RedisBackedExpiringSet(
                redis_url=self.redis_url,
                prefix=f"rare:nonce:full_issue:{namespace}",
                capacity=replay_cache_capacity,
            ),
            seen_upgrade_nonces=_RedisBackedExpiringSet(
                redis_url=self.redis_url,
                prefix=f"rare:nonce:upgrade:{namespace}",
                capacity=replay_cache_capacity,
            ),
            seen_platform_jtis=_RedisBackedExpiringSet(
                redis_url=self.redis_url,
                prefix=f"rare:platform:jti:{namespace}",
                capacity=replay_cache_capacity,
            ),
        )
        challenge_store = InMemoryChallengeStore(
            platform_register_challenges=_RedisBackedExpiringMap(
                redis_url=self.redis_url,
                prefix=f"rare:challenge:platform_register:{namespace}",
                capacity=challenge_cache_capacity,
            )
        )
        session_store = InMemorySessionStore(
            hosted_session_keys=_RedisBackedExpiringMap(
                redis_url=self.redis_url,
                prefix=f"rare:session:hosted:{namespace}",
                capacity=session_cache_capacity,
            )
        )
        return replay_store, challenge_store, session_store

    def readiness(self) -> dict[str, Any]:
        if not self.redis_url:
            return {"status": "ok", "backend": "memory-fallback"}
        try:
            import redis
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("redis is required for RedisReplayStore") from exc
        client = redis.Redis.from_url(self.redis_url, decode_responses=False)
        client.ping()
        return {"status": "ok", "backend": "redis"}

    @classmethod
    def clear_namespace(cls, namespace: str) -> None:
        with cls._lock:
            cls._replay_by_namespace.pop(namespace, None)


class PostgresRedisStateStore:
    """
    Composite store that combines Postgres-like durable state and Redis-like replay state.
    """

    def __init__(
        self,
        *,
        namespace: str,
        postgres_dsn: str | None = None,
        redis_url: str | None = None,
        postgres_store: PostgresStateStore | None = None,
        redis_replay_store: RedisReplayStore | None = None,
    ) -> None:
        self.namespace = namespace
        self.postgres_store = postgres_store or PostgresStateStore(dsn=postgres_dsn)
        self.redis_replay_store = redis_replay_store or RedisReplayStore(redis_url=redis_url)

    @classmethod
    def clear_namespace(cls, namespace: str) -> None:
        PostgresStateStore.clear_namespace(namespace)
        RedisReplayStore.clear_namespace(namespace)

    def open(
        self,
        *,
        replay_cache_capacity: int,
        session_cache_capacity: int,
        challenge_cache_capacity: int,
        public_rate_counter_capacity: int,
    ) -> RareStateHandles:
        agent_store, upgrade_store = self.postgres_store.open(
            namespace=self.namespace,
            challenge_cache_capacity=challenge_cache_capacity,
        )
        replay_store, challenge_store, session_store = self.redis_replay_store.open(
            namespace=self.namespace,
            replay_cache_capacity=replay_cache_capacity,
            session_cache_capacity=session_cache_capacity,
            challenge_cache_capacity=challenge_cache_capacity,
            public_rate_counter_capacity=public_rate_counter_capacity,
        )
        return _compose_handles(
            agent_store=agent_store,
            upgrade_store=upgrade_store,
            replay_store=replay_store,
            challenge_store=challenge_store,
            session_store=session_store,
        )

    def load_snapshot(self) -> dict[str, Any] | None:
        return self.postgres_store.load_snapshot(namespace=self.namespace)

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.postgres_store.save_snapshot(namespace=self.namespace, snapshot=snapshot)

    def snapshot_revision(self) -> int | None:
        return self.postgres_store.snapshot_revision(namespace=self.namespace)

    def readiness(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "backend": "postgres_redis",
            "postgres": self.postgres_store.readiness(),
            "redis": self.redis_replay_store.readiness(),
        }


class SqliteStateStore(InMemoryStateStore):
    """
    Durable local state store backed by SQLite.

    This keeps the existing in-memory handles inside RareService while providing snapshot
    persistence across restarts for production-like local and CI environments.
    """

    def __init__(self, *, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rare_state_snapshot (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    snapshot_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

    def load_snapshot(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM rare_state_snapshot WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return json.loads(str(row[0]))

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rare_state_snapshot (id, snapshot_json, updated_at)
                VALUES (1, ?, strftime('%s','now'))
                ON CONFLICT(id) DO UPDATE SET
                    snapshot_json=excluded.snapshot_json,
                    updated_at=excluded.updated_at
                """,
                (payload,),
            )
            _project_snapshot_to_sqlite(connection, snapshot)

    def snapshot_revision(self) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT updated_at FROM rare_state_snapshot WHERE id = 1"
            ).fetchone()
        return int(row[0]) if row is not None else None

    def readiness(self) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ok", "backend": "sqlite", "path": str(self.path)}
