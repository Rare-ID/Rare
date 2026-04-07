# Agent 快速开始

对 Agent 来说，Rare 目前支持的公开接口是 CLI：

- `rare`
- `rare-signer`

`rare_agent_sdk` 下的 Python 模块不是公开稳定 API。

## 安装

```bash
pip install rare-agent-sdk
```

## 托管签名模式

```bash
rare register --name alice --rare-url https://api.rareid.cc
rare refresh-attestation --rare-url https://api.rareid.cc
rare show-state --paths
```

## 自托管模式

```bash
rare-signer
rare register --name alice --key-mode self-hosted
rare show-state --paths
```

## 登录第三方平台

```bash
rare login \
  --aud platform.example.com \
  --platform-url http://127.0.0.1:3000/rare \
  --public-only
```

如果平台已注册且你需要 full attestation：

```bash
rare issue-full-attestation --aud platform.example.com
rare login --aud platform.example.com --platform-url http://127.0.0.1:3000/rare
```

