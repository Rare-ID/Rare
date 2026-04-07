# Env And Modes

When the skill is invoked for a real integration task, the agent should first give the human a short mode choice:

- `public-only`: recommended default, lowest setup cost
- `full-mode`: only for platform registration, full attestation, raw governance, or event ingest

If the human does not choose, proceed with `public-only`.

## Public-only quickstart

Start here unless the user explicitly asks for full-mode.

- Required env: `PLATFORM_AUD`
- Optional env: `RARE_BASE_URL`
- Optional env: `RARE_SIGNER_PUBLIC_KEY_B64`
- Default `RARE_BASE_URL`: `https://api.rareid.cc`
- `RARE_SIGNER_PUBLIC_KEY_B64` should normally be omitted so the SDK can resolve it from Rare JWKS

Public-only still requires:

- one-time challenge nonce consumption
- delegation replay protection
- identity/delegation triad consistency
- local verification of attestation and delegation artifacts

Public-only caps effective governance to `L1`.

## Full-mode

Only switch to full-mode when the user explicitly needs:

- platform registration
- platform-bound full attestation
- production governance on raw `L0/L1/L2`
- negative event ingest

When moving to full-mode, keep the quickstart auth routes in place and extend them rather than rewriting them from scratch.
