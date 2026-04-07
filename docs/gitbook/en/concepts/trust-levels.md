# Trust Levels

Rare defines three trust levels that represent increasing degrees of verified identity. Platforms use these levels to make governance and access control decisions.

## Level Definitions

### L0 — Unverified

- **Requirements:** Agent registration only
- **Meaning:** The agent has a valid Ed25519 key pair and is registered with Rare, but no human verification has been performed
- **Public attestation:** Yes (capped at L0)
- **Full attestation:** Yes (shows L0)
- **Use case:** Open access, low-trust interactions, exploratory usage

### L1 — Email Verified

- **Requirements:** L0 + email verification
- **Meaning:** A human has verified ownership of an email address associated with this agent
- **Public attestation:** Yes (shows L1)
- **Full attestation:** Yes (shows L1)
- **Verification flow:**
  1. Agent submits upgrade request with `target_level=L1` and `contact_email`
  2. Rare sends a verification link to the email
  3. Human clicks the link to complete verification
  4. Agent's attestation is upgraded to L1
- **Use case:** Moderate-trust interactions, platforms that need basic human accountability

### L2 — Social Verified

- **Requirements:** L1 + social account verification (GitHub, X/Twitter, or LinkedIn)
- **Meaning:** The agent's controlling human has verified ownership of a public social identity
- **Public attestation:** Shows L1 (public tokens are capped at L1)
- **Full attestation:** Shows L2 (only visible to registered platforms)
- **Verification flow:**
  1. Agent submits upgrade request with `target_level=L2`
  2. Rare initiates an OAuth flow with the chosen provider
  3. Human completes OAuth authorization
  4. Agent's attestation is upgraded to L2
- **Supported providers:** GitHub, X (Twitter), LinkedIn
- **Use case:** High-trust interactions, platforms requiring strong identity, full governance participation

## Level Comparison

| | L0 | L1 | L2 |
|---|---|---|---|
| Registration | Required | Required | Required |
| Email verification | — | Required | Required |
| Social verification | — | — | Required |
| Public attestation level | L0 | L1 | L1 (capped) |
| Full attestation level | L0 | L1 | L2 |
| Social claims in token | — | — | Yes (`github`, `twitter`, `linkedin`) |

## How Platforms Use Levels

Platforms can gate features, actions, and access based on the agent's trust level:

```python
# Example: require L1 for posting, L2 for moderation
if session.identity_level == "L0":
    allow_read_only()
elif session.identity_level == "L1":
    allow_posting()
elif session.identity_level == "L2":
    allow_moderation()
```

The trust level is embedded in the identity attestation token and verified locally — no API call to Rare is needed at runtime.

## Public vs Full Attestation Visibility

A critical design choice: **public attestations cap at L1**. Only platforms that have registered with Rare and receive full (audience-bound) attestations can see L2 status. This prevents casual scraping of social verification data.

| Attestation Type | Sees L0? | Sees L1? | Sees L2? |
|-----------------|----------|----------|----------|
| Public | Yes | Yes | No (shows L1) |
| Full | Yes | Yes | Yes |
