# Rare: An Agent-Native Identity & Trust Protocol

### Draft v0.1

## Abstract

Rare is an open protocol for **agent-native identity, trust signaling, and capability authorization**.
Instead of platform-issued accounts, Rare uses **public keys as identities** and **cryptographic signatures as proof of action**.

Agents can authenticate across platforms without registration, obtain short-lived capability sessions, and carry portable trust attestations such as L0/L1/L2 levels.

Rare separates **identity, trust, and platform governance**, enabling interoperable agent ecosystems without centralized identity providers.

---

# 1. Motivation

The rise of autonomous agents introduces new challenges:

* Agents interact across multiple platforms and APIs
* Platforms must distinguish legitimate agents from automated abuse
* Existing identity systems assume human-driven login and centralized accounts

Traditional solutions require:

* manual registration
* OAuth integrations
* platform-specific trust systems

This leads to **fragmented identities, duplicated governance, and poor interoperability**.

Rare proposes a minimal protocol where:

* **identity belongs to the agent**
* **trust signals are portable**
* **platforms remain sovereign in policy**

---

# 2. Design Principles

Rare is designed with the following principles:

### Agent-Native

Agents should authenticate using cryptographic identity without requiring human-operated accounts.

### Minimal Protocol

Rare defines only the primitives necessary for interoperability:

* identity
* attestations
* capability sessions

Everything else is left to applications.

### Portable Trust

Trust signals should be **portable across platforms** while allowing each platform to apply its own policies.

### Platform Sovereignty

Rare does not enforce global rules.
Platforms retain full control over access policies and governance.

### Cryptographic Verification

All identity and trust signals are verifiable using signatures.

---

# 3. Core Concepts

## 3.1 Agent Identity

Each agent is identified by a public key.

```
Public key = Agent identity
Private key = Control
```

Agents sign requests with their private key to prove identity.

---

## 3.2 Trust Levels

Rare defines portable trust signals that platforms may choose to recognize.

Example reference levels:

| Level | Description                                                                 |
| ----- | --------------------------------------------------------------------------- |
| L0    | Registered agent identity                                                   |
| L1    | Agent connected to a human actor                                            |
| L2    | Agent bound to verified external assets (e.g., social or platform accounts) |

Trust levels are represented as **attestations** signed by an issuer.

Platforms decide how to interpret them.

---

## 3.3 Capability Sessions

Agents exchange signed identity proofs for **short-lived session tokens** issued by platforms.

Sessions represent **capabilities**, not identities.

Example capabilities:

* API access
* rate-limit upgrades
* sensitive operations

Sessions are:

* short-lived
* revocable
* scoped

---

## 3.4 Attestations

Attestations are signed statements about an agent identity.

Example claims:

* trust level
* asset binding
* verification results

Attestations are portable and verifiable across platforms.

---

# 4. Protocol Architecture

Rare separates responsibilities across three actors:

```
Agent
   │
   │ signed identity proof
   ▼
Platform
   │
   │ issues capability session
   ▼
Session-based actions
```

Attestations may be issued by identity systems or trusted verifiers.

Platforms may optionally report negative events or trust updates.

Rare does not enforce global consensus on trust.

---

# 5. Governance and Evolution

Rare evolves through **Rare Improvement Proposals (RIP)**.

RIPs define interoperable specifications including:

* identity formats
* attestation schemas
* session token structures
* governance mechanisms

RIPs follow an open proposal process and become stable once widely implemented.

---

# 6. Security Considerations

Rare relies on cryptographic primitives for identity verification.

Key considerations include:

* protection against replay attacks
* secure session issuance
* limited scope capabilities
* revocable attestations
* privacy-preserving verification

Implementations should follow established best practices in key management and token security.

---

# 7. Conclusion

Rare introduces a minimal identity and trust layer designed for autonomous agents.

By separating identity, trust signals, and platform governance, Rare enables interoperable agent ecosystems while preserving platform autonomy.

Rare does not attempt to replace existing platforms or authentication systems.
Instead, it provides a lightweight protocol for **agent-native identity and capability authorization**.

---

# Acknowledgements

Rare draws inspiration from earlier decentralized protocol designs that prioritize simplicity, cryptographic identity, and open evolution.

In particular, we thank the creators of **Nostr** for demonstrating how minimal protocols based on public-key identity and extensible proposal processes can enable open, interoperable ecosystems.