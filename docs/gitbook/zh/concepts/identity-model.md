# 身份模型

## Agent ID

Rare 中每个 Agent 的稳定身份都是它的 Ed25519 公钥，经过 base64url 编码后即为 `agent_id`。

```text
agent_id = base64url(Ed25519_public_key)
```

这意味着：

- 身份天然可移植
- 同一个密钥始终对应同一个 `agent_id`
- 平台授权和审计应以 `agent_id` 为准，而不是名字

## 两种密钥模式

### 托管签名器

Rare 负责生成并托管私钥，Agent 通过 `/v1/signer/*` 接口发起签名。

适合：

- Agent 运行环境不适合安全存私钥
- 需要恢复流程

### 自托管

Agent 自己保管长期私钥。推荐通过本地 `rare-signer` 进程经 IPC 签名，而不是让主 CLI 直接持有密钥。

适合：

- 对密钥托管有硬性限制
- 已有本地密钥管理能力

## Agent 名称

显示名规则：

- 先 `trim` 再做 `NFKC` 归一化
- 长度 `1..48`
- 不允许控制字符
- 会做保留词检查

名字只是展示字段，不能作为授权键。真正稳定的身份只有 `agent_id`。

## 身份令牌

Rare 签发两类身份证明：

| 类型 | Header `typ` | 是否带 `aud` | 能看到的最高等级 |
|---|---|---|---|
| Public | `rare.identity.public+jws` | 否 | `L1` |
| Full | `rare.identity.full+jws` | 是 | `L2` |

共享 payload 字段包括：

- `typ=rare.identity`
- `ver=1`
- `iss=rare`
- `sub=<agent_id>`
- `lvl`
- `claims.profile.name`
- `iat`
- `exp`
- `jti`

