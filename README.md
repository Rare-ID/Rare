# Rare Workspace (Split Repos)

Rare 是一个面向 AI Agent 的身份与信任基础设施，核心能力包括：
- 可验证身份（Identity Attestation）
- 可治理权限（L0/L1/L2 分层策略）
- 可追溯行为（Challenge + Delegation + 审计字段）

当前仓库已切换为五包工作区（split-repo + shared packages），不再保留旧目录兼容层。

其中 Python 侧的依赖关系现在是：
- `rare-agent-sdk-python` 只依赖 `rare-identity-protocol`
- `rare-identity-core` 依赖 `rare-identity-protocol` 与 `rare-identity-verifier`
- `rare-identity-verifier` 依赖 `rare-identity-protocol`

## Workspace Layout

- `rare-identity-core/`: Core API 服务（FastAPI + Python）
- `rare-identity-protocol-python/`: 协议层共享包（Python）
- `rare-identity-verifier-python/`: verifier 共享包（Python）
- `rare-agent-sdk-python/`: Agent SDK + CLI（Python）
- `rare-platform-kit-ts/`: Platform Kit（TypeScript monorepo）
- `scripts/`: 工作区统一测试与依赖脚本

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -r ./rare-identity-protocol-python/requirements-test.lock
pip install -r ./rare-identity-verifier-python/requirements-test.lock
pip install -e "./rare-identity-protocol-python[test]"
pip install -e "./rare-identity-verifier-python[test]"
pip install -r ./rare-identity-core/requirements-test.lock
pip install -r ./rare-agent-sdk-python/requirements-test.lock
pip install -e "./rare-identity-core[test]"
pip install -e "./rare-agent-sdk-python[test]"
```

## Development Commands

一键回归：

```bash
./scripts/test_all.sh
```

覆盖率检查：

```bash
./scripts/test_cov_all.sh
```

可复现依赖锁定与审计：

```bash
./scripts/lock_deps.sh
./scripts/audit_deps.sh
```

语法级检查：

```bash
python -m compileall rare-identity-protocol-python rare-identity-verifier-python rare-identity-core rare-agent-sdk-python
```

## Document Index

- `Rare.md`: 总览与术语
- `FOR_AGENT.md`: Minimal guide for agents (hosted/self-hosted, actions, trust upgrades)
- `FOR_PLATFORM.md`: Minimal guide for platform integration (auth, action verification, onboarding, event ingest)
- `docs/deployment-gcp.md`: GCP external beta deployment assets and runtime contract
- `docs/sdk-release.md`: Python SDK / TypeScript Platform Kit release guide
- `docs/release-sop.md`: 正式发布 SOP（私有主仓 -> 公开仓 -> PyPI/npm）
- `rare-identity-core/docs/RIP_INDEX.md`: RIP 文档导航
- `rare-identity-protocol-python/README.md`: Python 协议包说明
- `rare-identity-verifier-python/README.md`: Python verifier 包说明
- `rare-identity-core/docs/rip-0001-identity-attestation.md`: 身份声明规范
- `rare-identity-core/docs/rip-0002-delegation.md`: Delegation 规范
- `rare-identity-core/docs/rip-0003-challenge-auth.md`: Challenge 认证规范
- `rare-identity-core/docs/rip-0005-platform-onboarding-and-events.md`: 平台接入与事件规范
- `rare-agent-sdk-python/README.md`: Python SDK/CLI 使用说明
- `rare-platform-kit-ts/QUICKSTART.md`: TypeScript 平台接入快速开始

## Current Baseline (2026-03-04)

本地执行结果：
- `./scripts/test_all.sh` 通过
- `./scripts/test_cov_all.sh` 通过
- `python3 scripts/validate_rip_docs.py` 通过
- `python3 -m compileall rare-identity-protocol-python rare-identity-verifier-python rare-identity-core rare-agent-sdk-python` 通过

注意：
- `rare-identity-core` 当前默认实现以内存数据结构为主，适合本地与集成测试；生产部署需外置持久化与分布式防重放存储。
