# AGENTS.md

## 项目概述

Rare 是一个面向 AI Agent 的身份与信任基础设施，目标是让 Agent 在真实世界执行动作时具备：

- 可验证身份（Identity Attestation）
- 可治理权限（基于 L0/L1/L2 的策略控制）
- 可追溯行为（Challenge + Delegation + 审计字段）

项目类型与技术栈：

- 语言：Python 3.11+
- API：FastAPI
- 密码学：Ed25519 / JWS（EdDSA）
- 测试：Pytest + FastAPI TestClient
- 包管理：`pip`（多包工作区）

架构形态（当前生效）：

- 三仓工作区（`rare-identity-core`、`rare-sdk-python`、`rare-thirdparty-moltbook-example`）
- **关键**：当前仓库已切换到 split-repo 工作区，无旧命名兼容层

---

## 开发命令（可直接执行）

### 1) 工作区初始化（推荐）

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -e "./rare-identity-core[test]"
pip install -e "./rare-sdk-python[test]"
pip install -e "./rare-thirdparty-moltbook-example[test]"
```

### 2) 启动服务

仅启动 Rare Core API：

```bash
cd rare-identity-core
uvicorn rare_api.main:app --reload --host 127.0.0.1 --port 8000
```

启动 Rare + 第三方平台联调网关（推荐本地联调）：

```bash
cd rare-thirdparty-moltbook-example
./scripts/run_local.sh
```

默认挂载路由：

- `http://127.0.0.1:8000/rare`
- `http://127.0.0.1:8000/platform`

### 3) 运行测试

工作区一键测试：

```bash
./scripts/test_all.sh
```

分仓测试：

```bash
(cd rare-identity-core && pytest -q)
(cd rare-sdk-python && pytest -q)
(cd rare-thirdparty-moltbook-example && pytest -q)
```

按关键用例快速回归：

```bash
(cd rare-identity-core && pytest -q tests/test_core.py -k "set_name or nonce")
(cd rare-thirdparty-moltbook-example && pytest -q tests/test_platform_integration.py -k "triad or replay or rate_limit")
```

### 4) 构建与产物检查

构建 wheel/sdist：

```bash
pip install build
(cd rare-identity-core && python -m build)
(cd rare-sdk-python && python -m build)
(cd rare-thirdparty-moltbook-example && python -m build)
```

语法/导入级检查（无额外依赖）：

```bash
python -m compileall rare-identity-core rare-sdk-python rare-thirdparty-moltbook-example
```

可选静态检查（建议在 CI 中启用）：

```bash
pip install ruff
ruff check rare-identity-core rare-sdk-python rare-thirdparty-moltbook-example
```

### 5) SDK/CLI 常用命令

```bash
cd rare-sdk-python
rare register --name alice
rare request-upgrade --level L1 --email alice@example.com
rare request-upgrade --level L2
rare start-social --request-id <upgrade_request_id> --provider github
rare grant-platform --aud platform
rare issue-full-attestation --aud platform
rare login --aud platform --platform-url http://127.0.0.1:8000/platform
rare login --aud platform --public-only
rare set-name --name alice-v2
rare refresh-attestation
rare show-state
```

---

## 项目结构

```text
.
├── rare-identity-core/                  # 身份核心仓
│   ├── services/rare_api/               # Rare API: self_register / set_name / refresh / signer
│   ├── libs/rare_identity_protocol/     # 协议层: challenge、token、crypto、name_policy
│   ├── libs/rare_identity_verifier/     # 验证器: identity/delegation 验证逻辑
│   ├── docs/                            # RIP 规范草案
│   └── tests/                           # Core 单元与接口测试
├── rare-sdk-python/                     # Agent SDK + CLI
│   ├── src/rare_sdk/                    # AgentClient、状态管理、CLI
│   └── tests/                           # SDK 与 CLI 测试
├── rare-thirdparty-moltbook-example/    # 第三方平台接入示例
│   ├── apps/moltbook_api/               # challenge/auth 完成、post/comment、rate limit
│   ├── apps/runtime.py                  # Rare 与平台服务拼装
│   ├── scripts/run_local.sh             # 本地联调入口（/rare + /platform）
│   └── tests/                           # 跨仓 E2E 集成测试
├── scripts/test_all.sh                  # 工作区测试入口
└── docs/                                # 根文档（用户流程、平台接入流程）
```

---

## 代码规范

### 通用规范

- 命名：`snake_case`（函数/变量）、`PascalCase`（类/数据模型）、`UPPER_SNAKE_CASE`（常量）
- 所有对外函数与服务方法必须带类型标注
- FastAPI 请求体统一使用 Pydantic `BaseModel`
- 异常映射统一由入口层 `_raise_http(...)` 完成，不在 handler 内散落状态码分支

### Rare 项目特有规范（必须遵守）

- **关键**：身份主键永远是 `agent_id`（Ed25519 公钥）；`name` 仅展示，不做唯一键
- **关键**：挑战签名串必须使用固定格式  
  `rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}`
- **关键**：改名签名串必须使用固定格式  
  `rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}`
- **关键**：平台授权签名串固定为  
  `rare-grant-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- **关键**：full attestation 签发签名串固定为  
  `rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- **关键**：升级请求签名串固定为  
  `rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}`
- **关键**：`name` 必须执行 `trim + NFKC` 归一化，长度 `1..48`，禁止控制字符，检查保留词
- **关键**：平台认证时必须做 identity triad 一致性校验  
  `auth_complete.agent_id == delegation.agent_id == attestation.sub`
- Token 约束：
  - Identity JWS header `typ` 只允许：
    - `rare.identity.public+jws`
    - `rare.identity.full+jws`
  - `rare.identity.public+jws` 不允许 `payload.aud`
  - `rare.identity.full+jws` 必须校验 `payload.aud==expected_aud`
  - Delegation JWS header `typ` 固定为 `rare.delegation+jws`
  - payload `ver` 当前固定为 `1`
  - verifier 对未知 claims 字段保持前向兼容（忽略未知字段）

### 安全红线

- ⚠️ 禁止提交私钥、会话 token、SDK 本地状态文件中的敏感字段
- ⚠️ 非必要不要改动签名 payload 格式；一旦改动必须同步更新 `rare-identity-core/docs/RIP` 与跨仓测试

---

## 测试策略

测试分层：

- 单仓单元/接口测试：各子仓 `tests/`
- 跨仓集成测试：`rare-thirdparty-moltbook-example/tests/test_platform_integration.py`
- 工作区回归：`./scripts/test_all.sh`

覆盖重点（必须有用例）：

- challenge nonce 一次性消费与重放拒绝
- delegation aud/scope/exp 校验
- identity attestation 的 `kid`、`typ(public/full)`、`lvl`、`aud`、`exp` 校验
- identity triad 一致性校验
- L0/L1/L2 频控策略（post/comment）
- set_name 的签名、防重放、速率限制
- L1/L2 升级流程（upgrade request、magic link、social state）签名与防重放

覆盖率门禁（建议写入 CI）：

- 总体行覆盖率 `>= 85%`
- `rare_identity_protocol` 与 `rare_identity_verifier` 覆盖率 `>= 95%`
- 涉及认证链路变更的 PR，新增/修改路径覆盖率目标 `100%`

覆盖率执行命令：

```bash
pip install pytest-cov
(cd rare-identity-core && pytest -q --cov=libs/rare_identity_protocol --cov=libs/rare_identity_verifier --cov=services/rare_api --cov-report=term-missing)
(cd rare-sdk-python && pytest -q --cov=src/rare_sdk --cov-report=term-missing)
(cd rare-thirdparty-moltbook-example && pytest -q --cov=apps/moltbook_api --cov-report=term-missing)
```

---

## 提交流程（建议）

1. 本地完成最小变更并补充测试
2. 运行 `./scripts/test_all.sh`
3. 运行构建与检查命令（至少 `compileall`）
4. 涉及协议字段/签名串变更时，同步更新 RIP 文档与跨仓集成测试
