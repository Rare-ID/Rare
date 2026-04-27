# Rare Security Threat Model

This document defines the first-pass security model for Rare verification work. It is not a proof of security. It is the checklist that turns protocol assumptions into tests and review targets.

## Assets

- Long-term agent identity key: the Ed25519 key whose public key is `agent_id`.
- Hosted signer management token: bearer credential for hosted signing operations.
- Rare identity signing keys: keys that issue public and full identity attestations.
- Rare delegation signing key: key that signs hosted-signer delegations.
- Platform session key: short-lived key delegated by an agent or Rare signer.
- Platform session token: platform-local bearer reference to an authenticated session.
- Replay stores: challenge nonce, delegation `jti`, action nonce, upgrade nonce, full-attestation nonce, platform event `jti`.
- Identity profile and risk state: governance state derived from upgrades and platform events.

## Trust Boundaries

- Agent to Rare API: registration, hosted signer, attestation issue, upgrade requests.
- Agent to platform: auth challenge completion and signed actions.
- Platform to Rare API: platform registration and negative event ingest.
- Verifier to JWKS: Rare signing key discovery and key rotation.
- Admin to Rare API: identity profile and operational controls.

## Primary Attack Classes

| Attack | Expected Defense | Verification Target |
| --- | --- | --- |
| Mixed identity artifacts | Triad consistency: `auth_complete.agent_id == delegation.agent_id == attestation.sub` | Platform kit auth completion tests |
| Challenge replay | One-time challenge nonce consumption | Platform challenge store tests |
| Delegation replay | One-time delegation `jti` claim until expiry | Platform replay store tests |
| Action replay | One-time action nonce per session | Platform action verification tests |
| Audience confusion | Exact `aud` match on delegation and full attestation | Verifier and platform tests |
| Public/full token confusion | Exact header `typ` and public token without `aud` | Verifier tests |
| Malformed agent identity | `agent_id` and `sub` must be Ed25519 public keys | Python and TypeScript verifier tests |
| Unknown signing key | Unknown `kid` must reject after resolver miss | Verifier tests |
| Expiry bypass | `iat`/`exp` checked with bounded skew | Verifier and action tests |
| Scope escalation | Required action scope must be present | Delegation verifier tests |
| Hosted token abuse | Management token is revocable and bound to one agent | Core service tests |
| Platform event poisoning | Platform event token signature, replay, idempotency, category validation | Core ingest tests |

## Non-Goals For The First Pass

- Formal cryptographic proof.
- Browser UI threat modeling.
- Production infrastructure proof beyond application-level configuration checks.
- Human identity provider security guarantees beyond validating Rare's local handling of provider snapshots.

## Review Questions

Every protocol change should answer:

1. Which identity is being proven?
2. Which key signs this proof?
3. Which audience is this proof valid for?
4. Which nonce or `jti` prevents replay?
5. Which verifier must reject mixed or malformed artifacts?
6. Which tests prove the rejection path?
