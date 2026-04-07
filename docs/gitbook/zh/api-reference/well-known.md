# Well-Known

## GET /.well-known/rare-keys.json

返回 Rare 的 JWKS，平台可据此本地验证 Rare 签名的身份证明和委托令牌。

## 常见字段

| 字段 | 说明 |
|---|---|
| `issuer` | 一般为 `rare` |
| `kid` | 密钥 ID |
| `kty` | `OKP` |
| `crv` | `Ed25519` |
| `x` | 公钥的 base64url |
| `retire_at` | 计划退役时间 |
| `rare_role` | Rare 角色提示，如 `identity` 或 `delegation` |

## 缓存建议

1. 启动时拉取并缓存
2. 校验 token 时按 `kid` 查找
3. 本地未命中时立即刷新一次
4. 仍找不到就拒绝 token

