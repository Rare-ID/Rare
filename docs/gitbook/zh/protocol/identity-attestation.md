# 身份证明（RIP-0001）

Rare 身份证明是由 Rare 签名、由平台本地验证的 JWS。

## 允许的类型

- `rare.identity.public+jws`
- `rare.identity.full+jws`

旧的 `rare.identity+jws` 在 v1 中无效。

## 共享 Payload 规则

每个证明都包含：

- `typ=rare.identity`
- `ver=1`
- `iss=rare`
- `sub=<agent_id>`
- `lvl`
- `claims.profile.name`
- `iat`
- `exp`
- `jti`

## Public 证明

- 不带 `aud`
- 最高只显示到 `L1`

## Full 证明

- 必须带 `aud=<platform_aud>`
- 显示真实等级

## 校验要求

平台必须：

1. 通过 `kid` 找到公钥
2. 校验 Ed25519 JWS 签名
3. 校验 `typ`、`ver`、`iss`、`sub`、`lvl`、`iat`、`exp`
4. 按 token 类型校验 `aud`
5. 允许最多 30 秒时钟偏差
6. 忽略未知 claims

