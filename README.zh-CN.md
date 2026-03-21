<p align="center">
  <img src="docs/assets/rare-banner.svg" alt="Rare banner" width="900" />
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://rareid.cc">
    <img alt="Website" src="https://img.shields.io/badge/Website-rareid.cc-111111?style=for-the-badge" />
  </a>
  <a href="https://github.com/Rare-ID/Rare">
    <img alt="GitHub" src="https://img.shields.io/badge/GitHub-Rare--ID%2FRare-111111?style=for-the-badge" />
  </a>
  <a href="https://x.com/rareaip">
    <img alt="X" src="https://img.shields.io/badge/X-@rareaip-111111?style=for-the-badge" />
  </a>
  <a href="https://discord.gg/SNWYHS4nfW">
    <img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20Community-111111?style=for-the-badge" />
  </a>
</p>

## 为什么是 Rare

现在互联网的身份系统主要是为人设计的：邮箱、密码、OAuth 账号。但 Agent 需要另一套模型。Agent 用密钥标识自己，用签名证明控制权，还需要能在不同产品之间流动的信任和权限。Rare 把这些能力整理成公开协议、参考服务、Agent CLI 和平台集成工具。

## 核心模型

- `agent_id` 永远是 Ed25519 公钥。
- 控制权通过签名证明，而不是通过 bearer 身份 token 证明。
- Rare 的信任表达通过 attestation 完成，例如 `L0`、`L1`、`L2`。
- 平台校验的是被 delegation 的 session key，而不是直接拿长期身份私钥做交互。
- 防重放和固定签名输入是协议红线，不是实现细节。

## Rare 提供什么

- 可在不同产品和平台间流动的 Agent 身份
- 可供平台治理使用的 trust signaling
- 用短期 capability session 替代长期共享密钥
- 公开的协议规范、测试向量和参考实现

## Quick Start

### Agent 快速开始

把下面这句 prompt 直接贴给你的 Agent：

```text
Read https://www.rareid.cc/skill.md and follow the instructions to register Rare
```

如果你想让 Agent 接入 Rare，最直接的入口就是 `https://www.rareid.cc/skill.md`。这个页面已经给了 Agent 需要遵循的完整指令。

目前 Rare 提供两条公开的 Agent 操作路径：

- CLI 优先：`skills/rare-agent-cli/`
- curl 优先：`skills/rare-agent/`

当前公开支持的 Agent 接口是 `rare` / `rare-signer` CLI。`rare_agent_sdk` 的 Python import 不作为公开稳定接口承诺。

### Platform 快速开始

TypeScript：

```bash
pnpm add @rare-id/platform-kit-core @rare-id/platform-kit-client @rare-id/platform-kit-web
```

```ts
import { RareApiClient } from "@rare-id/platform-kit-client";
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKit,
} from "@rare-id/platform-kit-web";

const rareApiClient = new RareApiClient({
  rareBaseUrl: "https://api.rareid.cc",
});

const kit = createRarePlatformKit({
  aud: "platform",
  rareApiClient,
  challengeStore: new InMemoryChallengeStore(),
  replayStore: new InMemoryReplayStore(),
  sessionStore: new InMemorySessionStore(),
});
```

Python：

```bash
pip install rare-platform-sdk
```

```python
from rare_platform_sdk import (
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    RareApiClient,
    RarePlatformKitConfig,
    create_rare_platform_kit,
)

rare_api_client = RareApiClient(rare_base_url="https://api.rareid.cc")
kit = create_rare_platform_kit(
    RarePlatformKitConfig(
        aud="platform",
        rare_api_client=rare_api_client,
        challenge_store=InMemoryChallengeStore(),
        replay_store=InMemoryReplayStore(),
        session_store=InMemorySessionStore(),
    )
)
```

平台集成文档入口：

- `FOR_PLATFORM.md`
- `packages/platform/python/rare-platform-sdk-python/README.md`
- `packages/platform/ts/rare-platform-kit-ts/README.md`

## 使用场景

- 需要在多工具之间携带密码学身份的 Autonomous AI agents
- 需要让信任和历史跟随 Agent 迁移的 Agent marketplace
- 希望按 Rare trust level 动态开放能力的 API ecosystem
- 需要共享滥用和策略信号的跨平台治理系统

## 仓库结构

- `packages/shared/python/rare-identity-protocol-python/`：协议原语与签名输入
- `packages/shared/python/rare-identity-verifier-python/`：Python 校验工具
- `services/rare-identity-core/`：Rare API 的 FastAPI 参考实现
- `packages/agent/python/rare-agent-sdk-python/`：Agent CLI 和本地 signer
- `packages/platform/python/rare-platform-sdk-python/`：Python 平台 SDK 源码
- `packages/platform/ts/rare-platform-kit-ts/`：TypeScript 平台 SDK 源码
- `docs/rip/`：RIP 协议规范与测试向量
- `skills/rare-agent/`：curl-first Agent skill
- `skills/rare-agent-cli/`：CLI-first Agent skill
- `scripts/`：测试、校验、发布辅助脚本

## 文档入口

- `FOR_PLATFORM.md`：平台集成指南
- `docs/rip/RIP_INDEX.md`：协议索引
- `docs/release-guide.md`：发布流程
- `packages/agent/python/rare-agent-sdk-python/README.md`：Agent CLI 用法
- `packages/platform/python/rare-platform-sdk-python/README.md`：Python 平台 SDK 指南
- `packages/platform/ts/rare-platform-kit-ts/README.md`：TypeScript Platform SDK 指南

## 更多链接

- 官网：`https://rareid.cc`
- Whitepaper：`https://rareid.cc/whitepaper`
- Docs：`https://rareid.cc/docs`
- GitHub org：`https://github.com/Rare-ID`
- X：`https://x.com/rareaip`
- Discord：`https://discord.gg/SNWYHS4nfW`

## 本地开发

初始化工作区：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -r ./packages/shared/python/rare-identity-protocol-python/requirements-test.lock
pip install -r ./packages/shared/python/rare-identity-verifier-python/requirements-test.lock
pip install -e "./packages/shared/python/rare-identity-protocol-python[test]"
pip install -e "./packages/shared/python/rare-identity-verifier-python[test]"
pip install -r ./services/rare-identity-core/requirements-test.lock
pip install -r ./packages/agent/python/rare-agent-sdk-python/requirements-test.lock
pip install -r ./packages/platform/python/rare-platform-sdk-python/requirements-test.lock
pip install -e "./services/rare-identity-core[test]"
pip install -e "./packages/agent/python/rare-agent-sdk-python[test]"
pip install -e "./packages/platform/python/rare-platform-sdk-python[test]"
```

运行标准检查：

```bash
python scripts/validate_rip_docs.py --strict
python scripts/check_repo_hygiene.py
./scripts/test_all.sh
python -m compileall packages/shared/python/rare-identity-protocol-python packages/shared/python/rare-identity-verifier-python services/rare-identity-core packages/agent/python/rare-agent-sdk-python packages/platform/python/rare-platform-sdk-python
```

## 贡献

请查看 `CONTRIBUTING.md`、`SECURITY.md` 和 `SUPPORT.md`。
