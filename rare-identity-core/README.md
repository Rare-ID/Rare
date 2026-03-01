# rare-identity-core

Rare Identity 核心仓，提供：

- Rare API (`/v1/agents/*`, `/.well-known/rare-keys.json`)
- Rare signer API (`/v1/signer/*`) for hosted key signing
- Identity Library API (`/v1/identity-library/*`) for profile/subscription
- Identity/Delegation 协议实现 (`rare_identity_protocol`)
- Verifier (`rare_identity_verifier`)

## Run

```bash
pip install -e .[test]
uvicorn rare_api.main:app --reload
```

## Test

```bash
pytest -q
```
