# 密钥轮换（RIP-0004）

Rare 通过 JWKS 暴露签名公钥，让平台在密钥轮换时无需手工改配置。

## 端点

```text
GET /.well-known/rare-keys.json
```

每个 key 项通常包含：

- `kid`
- `kty=OKP`
- `crv=Ed25519`
- `x`
- `retire_at`
- 可选 `rare_role`

## 轮换要求

1. 新密钥启用前必须先发布
2. 新旧密钥至少重叠 7 天
3. 旧 token 未过期前，退役密钥应继续出现在 JWKS 中

## 校验器缓存策略

1. 缓存 1 到 24 小时
2. 遇到未知 `kid` 时立即刷新一次
3. 仍找不到则拒绝 token

