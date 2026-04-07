# 平台 SDK 快速开始

这是 Rare 平台接入的最短路径。

即使是 quick start，也仍然保留核心安全保证：

- challenge nonce 一次性消费
- 本地验证 identity attestation
- 验证 delegation token
- 强制三元一致性

## 你需要实现什么

平台最少需要三部分：

1. `POST /auth/challenge`
2. `POST /auth/complete`
3. 后续请求的 session 查询

在 public-only 模式下，这已经足够完成 Rare 登录并做到 `L1` 级别的治理。

## 必需环境变量

```bash
PLATFORM_AUD=platform.example.com
```

可选：

```bash
RARE_BASE_URL=https://api.rareid.cc
RARE_SIGNER_PUBLIC_KEY_B64=<rare signer public key>
PLATFORM_ID=platform-example-com
```

## 选择 SDK

- [TypeScript 入门](typescript/getting-started.md)
- [Python 入门](python/getting-started.md)

## 何时升级到 Full Mode

当你需要下面任一项时：

- 平台注册
- audience 绑定的 full attestation
- 原始 `L2` 可见性
- 负向事件上报
- 多实例共享持久化存储

详见：[完整模式](full-mode.md)

