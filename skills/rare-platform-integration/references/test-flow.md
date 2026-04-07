# Local Test Flow

After wiring Rare into the target app, give the user a concrete validation flow.

## Minimum validation

```bash
rare register --name alice
rare login --aud <platform_aud> --platform-url http://127.0.0.1:<port>/rare --public-only
```

Confirm:

- challenge route returns nonce/aud/timestamps
- auth complete returns a platform session token
- the app can read the authenticated session on a protected route

## If the app verifies delegated actions

Also verify:

- a signed action succeeds once
- replaying the same action nonce fails

## If the user asks for production guidance

Call out:

- switch off in-memory stores
- keep `PLATFORM_AUD` stable
- use full-mode only after platform registration is complete
