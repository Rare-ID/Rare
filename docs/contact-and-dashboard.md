# Stats Script And Email UX Plan

## 1. Stats

Do not keep a public dashboard in `rare-identity-core`.

Use a local script instead:

- Script: `scripts/show_stats.py`
- Reads existing admin APIs:
  - `GET /v1/admin/agents`
  - `GET /v1/admin/platforms`
- Aggregates:
  - total agents
  - L0 / L1 / L2
  - total platforms
  - latest registration times

Token strategy:

- First try `RARE_ADMIN_TOKEN`
- If unset, load `rare-core-api-prod-admin-token` from GCP Secret Manager

This keeps the API unchanged and avoids adding a public or semi-public admin page.

## 2. Inbox Email

SendGrid should remain the outbound sender for transactional mail:

- `noreply@rareid.cc`

Inbound mail should use a separate receiving address:

- `contact@rareid.cc`

Recommended setup:

- Cloudflare Email Routing
- Forward `contact@rareid.cc` to `0xsid.fan@gmail.com`

Optional aliases:

- `hello@rareid.cc`
- `security@rareid.cc`

## 3. Email UX

Current behavior is too raw:

- SendGrid payload is plain text only
- Verification links land on JSON API responses
- timestamps are machine-oriented

Recommended upgrade:

1. Keep plain text as fallback.
2. Add HTML email templates for:
   - L1 verification
   - hosted token recovery
3. Set `Reply-To: contact@rareid.cc`.
4. Replace JSON-facing verification responses with HTML result pages:
   - success
   - expired
   - invalid / already used

## 4. Human Time

Keep Unix timestamps internally, but format them for people in scripts and HTML:

- absolute: `Mar 12, 2026, 8:27 PM UTC+08:00`
- relative: `2 minutes ago`

Apply this to:

- stats script output
- email copy
- verification result pages
