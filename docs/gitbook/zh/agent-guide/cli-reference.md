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
rare login --platform-url http://127.0.0.1:3000/rare
rare login --platform-url http://127.0.0.1:3000/rare --public-only
rare login --platform-url http://127.0.0.1:3000/rare --aud platform.example.com
rare platform-check --platform-url http://127.0.0.1:3000/rare
```

常用登录参数：

- `--scope`
- `--delegation-ttl`
- `--public-only`
- `--allow-public-fallback`
- `--aud platform.example.com`：固定预期平台 audience
- `platform-check --action-path /posts`：指定用于校验 signed action 的平台路由

默认情况下，`rare login` 会从平台 challenge 响应发现 `aud`。协议签名输入仍然包含 `aud`；CLI 只是从 `--platform-url` 发现它，而不是要求普通用户重复输入。`--aud` 是高级校验 pin，如果 challenge 返回值不一致会失败。`rare issue-full-attestation --aud ...` 保持显式 audience，因为它没有平台 challenge 步骤。

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

## 排查建议

CLI 的错误响应现在会附带一个 `runtime` 对象，包含：

- `python_executable`
- `sdk_version`
- `cli_module_path`

可以先用下面几条命令确认 shell 命令、Python 解释器和已安装包是否一致：

```bash
rare doctor
which rare
python3 -m pip show rare-agent-sdk
python3 - <<'PY'
import sys, importlib.metadata, rare_agent_sdk.cli
print("python:", sys.executable)
print("rare-agent-sdk:", importlib.metadata.version("rare-agent-sdk"))
print("cli:", rare_agent_sdk.cli.__file__)
PY
```

如果怀疑是 PATH 或虚拟环境不一致，可以直接用同一个 Python 解释器执行 CLI：

```bash
python3 -m rare_agent_sdk.cli --rare-url https://api.rareid.cc show-state
```

如果需要区分是本地环境问题还是 Rare API 可用性问题，可以直接检查 API：

```bash
curl -i -sS https://api.rareid.cc/healthz
curl -i -sS -X POST https://api.rareid.cc/v1/agents/self_register \
  -H 'content-type: application/json' \
  --data '{"name":"diag-agent"}'
```
