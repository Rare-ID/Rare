# Overview

Rare is a public protocol for portable AI agent identity. It provides a complete identity lifecycle for autonomous AI agents: registration, authentication, trust attestation, and cross-platform governance.

## The Problem

Most internet identity systems are built for humans: emails, passwords, OAuth accounts, and session cookies. AI agents don't have email addresses or browsers. They need identity that is:

- **Key-based** — agents identify with cryptographic keys, not credentials
- **Portable** — identity travels across products and platforms
- **Trust-layered** — platforms can make governance decisions based on verified trust levels
- **Session-oriented** — short-lived capabilities replace long-lived shared secrets

## How Rare Works

```
┌──────────┐     register      ┌──────────────┐
│  Agent   │ ────────────────▶ │   Rare API   │
│          │ ◀──────────────── │              │
│ Ed25519  │    attestation    │  Trust Store │
│ key pair │                   └──────┬───────┘
└────┬─────┘                          │
     │                                │
     │  login (challenge-response)    │ JWKS / key discovery
     │                                │
     ▼                                ▼
┌──────────────────────────────────────────┐
│              Platform                     │
│  - Verify attestation locally (JWS)      │
│  - Verify delegation token               │
│  - Enforce triad consistency             │
│  - Manage sessions                       │
└──────────────────────────────────────────┘
```

1. **Registration** — An agent generates an Ed25519 key pair. The public key becomes the `agent_id`. The agent registers with Rare and receives an identity attestation.

2. **Attestation** — Rare signs a JWS token attesting to the agent's identity and trust level (L0, L1, or L2). This token can be verified locally by any platform using Rare's published public keys.

3. **Platform Login** — When an agent logs into a platform, it completes a challenge-response flow. The platform verifies three things in a "triad consistency" check:
   - The auth challenge signature
   - The delegation token
   - The identity attestation

4. **Sessions** — The agent delegates a short-lived session key to the platform. Actions during the session are signed with this session key, not the agent's long-term identity key.

## Core Principles

| Principle | Description |
|-----------|-------------|
| **Keys, not credentials** | `agent_id` is the Ed25519 public key. No passwords, no bearer tokens for identity. |
| **Signatures, not tokens** | Control is proven through cryptographic signatures, not by presenting identity tokens. |
| **Local verification** | Platforms verify attestations and delegations locally using Rare's JWKS endpoint. No online API call required per login. |
| **Replay protection** | Every signing input includes a one-time nonce. Protocol-level replay rejection is mandatory. |
| **Forward compatibility** | Verifiers must ignore unknown claims. New fields can be added without breaking existing integrations. |
