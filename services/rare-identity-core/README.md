# rare-identity-core

Rare Identity 核心仓，提供：

- Rare API (`/v1/agents/*`, `/.well-known/rare-keys.json`)
- Rare signer API (`/v1/signer/*`) for hosted key signing (Bearer auth required)
- Identity Library API (`/v1/identity-library/*`) for profile/subscription
- 依赖共享协议包 `rare-identity-protocol`
- 依赖共享 verifier 包 `rare-identity-verifier`

## Install

```bash
pip install -e ../../packages/python/rare-identity-protocol-python[test]
pip install -e ../../packages/python/rare-identity-verifier-python[test]
pip install -e .[test]
```

可复现安装：

```bash
pip install -r ../../packages/python/rare-identity-protocol-python/requirements-test.lock
pip install -r ../../packages/python/rare-identity-verifier-python/requirements-test.lock
pip install -r requirements-test.lock
pip install -e ../../packages/python/rare-identity-protocol-python[test] --no-deps
pip install -e ../../packages/python/rare-identity-verifier-python[test] --no-deps
pip install -e .[test] --no-deps
```

## Run

```bash
uvicorn rare_api.main:app --reload
```

## Test

```bash
pytest -q
```

覆盖率检查：

```bash
python -m pytest -q tests/test_core.py --cov=services/rare_api --cov-report=term-missing
```

## Protocol Docs

- `docs/rip-0000-rip-process.md`
- `docs/RIP_INDEX.md`
- `docs/rip-0001-identity-attestation.md`
- `docs/rip-0002-delegation.md`
- `docs/rip-0003-challenge-auth.md`
- `docs/rip-0005-platform-onboarding-and-events.md`

## Production Note

当前默认实现以内存状态存储为主，适用于开发与测试。生产部署前需将身份、授权、升级、challenge、nonce/jti 等状态外置到持久化与分布式缓存层（见根仓 `docs/deployment-gcp.md`）。

当前工作区已新增 GCP Beta 部署资产，见根仓 `docs/deployment-gcp.md` 与 `../../infra/gcp/terraform/`。
