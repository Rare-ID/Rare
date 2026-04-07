# 升级流程

Rare 的信任升级是叠加在 Agent 密钥之上的人工参与流程。

## 等级

- `L0`：仅注册
- `L1`：邮箱验证
- `L2`：社交账号验证

## L1 邮箱升级

```bash
rare request-upgrade --level L1 --email alice@example.com
rare send-l1-link --request-id <request_id>
rare upgrade-status --request-id <request_id>
```

## L2 社交升级

```bash
rare request-upgrade --level L2
rare start-social --request-id <request_id> --provider github
```

支持的 provider：

- `x`
- `github`
- `linkedin`

## 状态流转

```text
human_pending -> verified -> upgraded
       |             |
       v             v
    expired       revoked
```

## 固定签名输入

```text
rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}
```

