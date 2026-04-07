# 平台 SDK 完整模式

Full mode 面向需要更强治理能力的生产平台。

## 何时需要

如果你需要：

- 看到真实 `L2`
- 平台注册
- `aud` 绑定的 full attestation
- 持久化 replay / challenge / session 存储
- 向身份库上报负向事件

就应该从 quick start 升级到 full mode。

## Full Mode 清单

1. 用持久化共享存储替换内存存储
2. 通过 DNS challenge 注册平台
3. 接受并验证 `full_identity_attestation`
4. 强制校验 full token 的 `aud == PLATFORM_AUD`
5. 按需接入负向事件上报

## 平台注册

先请求：

```text
POST /v1/platforms/register/challenge
```

完成 DNS TXT 配置后再调用：

```text
POST /v1/platforms/register/complete
```

