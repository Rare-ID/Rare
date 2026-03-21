# rare-identity-core

FastAPI reference implementation of the Rare API.

## Install

```bash
pip install -e ../../packages/shared/python/rare-identity-protocol-python[test]
pip install -e ../../packages/shared/python/rare-identity-verifier-python[test]
pip install -e .[test]
```

可复现安装：

```bash
pip install -r ../../packages/shared/python/rare-identity-protocol-python/requirements-test.lock
pip install -r ../../packages/shared/python/rare-identity-verifier-python/requirements-test.lock
pip install -r requirements-test.lock
pip install -e ../../packages/shared/python/rare-identity-protocol-python[test] --no-deps
pip install -e ../../packages/shared/python/rare-identity-verifier-python[test] --no-deps
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

## Protocol

Protocol specifications live at the repo root under `docs/rip/`.

## Note

当前默认实现以内存状态存储为主，适用于开发与测试。生产部署前需将身份、授权、升级、challenge、nonce/jti 等状态外置到持久化与分布式缓存层。
