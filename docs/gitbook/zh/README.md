# Rare 开发者文档

Rare 是一个用于 **可移植 AI Agent 身份** 的公开协议和平台。它用基于 Ed25519 密钥的身份体系取代了面向人类的身份系统（邮箱、密码、OAuth），专为自主 AI Agent 设计。

## Rare 提供什么

- **可移植的 Agent 身份** — Agent 可在不同产品和平台间携带身份
- **信任信号** — 平台利用 Rare 证明等级（L0/L1/L2）进行治理决策
- **短期能力会话** — 使用委托会话密钥而非长期共享密钥
- **公开协议规范** — 测试向量、参考实现和开放的 RIP 标准

## 本文档的目标读者

| 读者 | 从这里开始 |
|------|-----------|
| **平台开发者**（集成 Rare 登录） | [平台 SDK 快速开始](platform-sdk/quickstart.md) |
| **Agent 开发者**（注册身份） | [Agent 快速开始](agent-guide/quickstart.md) |
| **API 调用者**（直接调用 Rare 服务） | [API 参考](api-reference/overview.md) |
| **协议实现者**（构建兼容系统） | [协议规范](protocol/rip-index.md) |

## 关键资源

- 生产环境 API：`https://api.rareid.cc`
- GitHub：[Rare-ID/Rare](https://github.com/Rare-ID/Rare)
- 官网：[rareid.cc](https://rareid.cc)
- Discord：[社区](https://discord.gg/SNWYHS4nfW)
