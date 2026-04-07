# CLI 参考

## 全局参数

`rare` 常用全局参数：

- `--state-file`
- `--rare-url`
- `--platform-url`
- `--signer-socket`

## 身份管理

```bash
rare register --name alice
rare register --name alice --key-mode self-hosted
rare set-name --name alice-v2
rare refresh-attestation
rare show-state --paths
```

## 登录

```bash
rare issue-full-attestation --aud platform.example.com
rare login --aud platform.example.com --platform-url http://127.0.0.1:3000/rare
rare login --aud platform.example.com --platform-url http://127.0.0.1:3000/rare --public-only
```

常用登录参数：

- `--scope`
- `--delegation-ttl`
- `--public-only`
- `--allow-public-fallback`

## 升级

```bash
rare request-upgrade --level L1 --email alice@example.com
rare send-l1-link --request-id <request_id>
rare upgrade-status --request-id <request_id>
rare request-upgrade --level L2
rare start-social --request-id <request_id> --provider github
```

## 托管 Token 生命周期

```bash
rare rotate-hosted-token
rare revoke-hosted-token
rare recovery-factors
rare recover-hosted-token-email
rare recover-hosted-token-email-verify --token <token>
rare recover-hosted-token-social-start --provider x
rare recover-hosted-token-social-complete --provider x --snapshot-json '<json>'
```

## 本地签名器

```bash
rare-signer
rare signer-serve
```

