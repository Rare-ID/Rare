# 平台接入（RIP-0005）

RIP-0005 定义了平台注册、full attestation、升级流程和平台事件上报。

## 基于 DNS 的平台注册

第一步：

```text
POST /v1/platforms/register/challenge
```

第二步：

```text
POST /v1/platforms/register/complete
```

输入包括：

- `challenge_id`
- `platform_id`
- `platform_aud`
- `domain`
- `keys[]`

## 注册平台上的 Full Attestation

签发 full attestation 需要：

- 平台已经注册并处于 active
- 使用固定签名输入：
  `rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`

## 升级流程

L1：

- `POST /v1/upgrades/requests`
- `POST /v1/upgrades/l1/email/send-link`
- `POST /v1/upgrades/l1/email/verify`

L2：

- `POST /v1/upgrades/requests`
- `POST /v1/upgrades/l2/social/start`
- `GET /v1/upgrades/l2/social/callback`
- `POST /v1/upgrades/l2/social/complete`

## 平台负向事件 Token

要求：

- Header `typ=rare.platform-event+jws`
- Payload `typ=rare.platform-event`
- `aud=rare.identity-library`
- `(iss, jti)` 做重放保护
- `(iss, event_id)` 做幂等去重

允许的分类：

- `spam`
- `fraud`
- `abuse`
- `policy_violation`

