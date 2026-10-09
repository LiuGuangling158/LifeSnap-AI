# LifeSnap AI

English: [README.md](README.md) | 简体中文

![LifeSnap AI 概念主视觉](docs/assets/lifesnap-ai-demo-hero.png)

> 上图为演示概念视觉，不是应用真实截图。

LifeSnap AI 是一个本地优先的个人财务工作台，可将自然语言、收据图片和日常记录整理为可核对的操作。它更关注 Agent 在模型回答之后的工程闭环：知识检索、受限工具调用、人工确认、质量准入、运行监控与持续反馈，而非只展示一个聊天原型。

## 为什么做这个项目

许多 AI 记账演示停留在“识别文本”或“回答问题”。LifeSnap AI 覆盖完整的可控业务流程：

1. 录入账单、待办、日记、图片或消费问题。
2. 执行隐私检查、知识检索、意图路由和工具选择。
3. 先生成候选记录，不直接修改财务数据。
4. 由用户编辑、确认或丢弃候选记录。
5. 记录隐私安全的 Trace、用户反馈、评测证据和运行信号，用于持续改进。

## 项目亮点

| 领域 | 已实现能力 |
| --- | --- |
| 个人工作台 | 账单、预算与消费报告、待办、日记、附件、导入导出、快照和仪表盘 |
| 账单采集 | 手动记账、图片收据识别、重复检测、字段级候选核对，以及确认后保存 |
| Agent 运行时 | 意图路由、RAG 检索、function calling、模型/规则降级、执行步骤和隐私安全解释 |
| RAG 知识库 | 可编辑业务知识、默认 BM25、可选向量融合、检索测试、版本历史、重建索引和回滚 |
| 质量治理 | 离线准入评测、RAG 专项评测、线上影子评测、回归比较、版本快照和回滚控制 |
| 用户反馈闭环 | 用户反馈关联运行 Trace；管理员复核后可将脱敏样例晋升为回归用例 |
| 韧性与成本 | 有限重试、按服务商/模型熔断、本地降级、Token 与预估成本聚合、模型健康告警 |
| 运维能力 | SQLite 事务、持久化租约任务、幂等控制、审计事件、诊断、Prometheus 指标、告警状态与分层测试 |

## Agent 执行链路

```text
用户消息 / 图片
        |
隐私保护与附件校验
        |
RAG 检索（BM25，可选向量融合）
        |
意图路由（已配置时调用模型，否则使用确定性规则）
        |
Function Calling：知识检索 / 账单候选 / 待办 / 日记 / 消费分析
        |
候选记录会话、版本号与冲突控制
        |
用户编辑并明确确认或丢弃
        |
SQLite 持久化、审计事件、Agent Trace、指标与反馈闭环
```

模型返回并不等同于写入授权。所有会改动账单、待办或日记的工具都会先生成候选记录；只有用户明确确认后才会落库，过期候选版本会被拒绝写入。

## 架构概览

```text
frontend/                 静态双语 Web 客户端
    |
FastAPI 应用               API、中间件、校验与静态资源托管
    |
服务层                     Agent、RAG、OCR、报告、异步任务、可观测性
    |
SQLite + 受管文件          事务数据、候选记录、Trace 与审计数据
    |
可选外部服务               DeepSeek / SiliconFlow / Kimi / OpenAI 兼容 Embeddings
```

默认部署形态是本地单工作区。业务接口没有暴露注册或登录能力；RAG 写入、版本发布、任务控制和反馈复核等治理操作使用由服务端管理员密钥签发的短期管理员会话。

## 快速启动

### 前置条件

- 推荐 Python 3.12
- 前端浏览器测试推荐 Node.js 22
- 即使不配置外部模型，也可体验本地规则与检索降级能力

### 本地运行

```powershell
Copy-Item .env.example .env

Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

uvicorn app.main:app --host 127.0.0.1 --port 8023
```

打开 [http://127.0.0.1:8023](http://127.0.0.1:8023)。接口文档位于 [http://127.0.0.1:8023/docs](http://127.0.0.1:8023/docs)，Prometheus 格式指标位于 `/metrics`。

macOS 或 Linux 环境请使用 `python3 -m venv .venv` 与 `source .venv/bin/activate` 替代 PowerShell 激活命令。

## 可选 AI 服务配置

以 `.env.example` 为起点；不配置某类服务时，对应流程会使用本地降级能力。密钥只应保存在服务端环境中，不能提交到仓库。

| 需求 | 主要配置 |
| --- | --- |
| 聊天意图与 Agent 路由 | `LIFESNAP_LLM_PROVIDER`、`LIFESNAP_LLM_BASE_URL`、`LIFESNAP_LLM_MODEL`、`LIFESNAP_DEEPSEEK_CHAT_API_KEY` |
| 账单/待办/日记默认解析 | `LIFESNAP_DEFAULT_AI_PROVIDER`、`LIFESNAP_DEFAULT_AI_BASE_URL`、`LIFESNAP_DEFAULT_AI_MODEL`、`LIFESNAP_DEFAULT_AI_API_KEY` |
| 图片账单识别 | `LIFESNAP_OCR_PROVIDER`、`LIFESNAP_OCR_ENDPOINT`、`LIFESNAP_OCR_MODEL`、`LIFESNAP_IMAGE_BILL_API_KEY` |
| 语义 RAG 融合 | `LIFESNAP_RAG_EMBEDDING_BASE_URL`、`LIFESNAP_RAG_EMBEDDING_MODEL`、`LIFESNAP_RAG_EMBEDDING_API_KEY` |
| 模型韧性与成本 | `LIFESNAP_MODEL_MAX_RETRIES`、`LIFESNAP_MODEL_CIRCUIT_FAILURE_THRESHOLD`、每百万 Token 输入/输出成本配置 |
| 管理员治理 | `LIFESNAP_ADMIN_KEY` |

模型调用网关只对短暂故障重试；连续最终失败会打开临时熔断器，并在支持的流程中回退到本地规则。模型用量按服务商与模型聚合，指标不保存提示词、响应正文、图片或密钥。

## 管理与质量闭环

**管理员页面**提供无需编辑 JSON 的知识库与 Agent 治理操作：

- 编辑、检索测试、版本化、重建索引、重置和回滚 RAG 知识。
- 运行离线准入评测和可选的线上影子评测。
- 创建、发布或回滚绑定 RAG 与模型运行指纹的 Agent 版本快照。
- 查看异步任务、Trace、告警、模型韧性和聚合成本信息。
- 复核用户反馈。只有管理员人工填写的脱敏样例及预期意图，才能晋升为回归评测用例；原始用户对话不会被复制到评测集。

离线准入门禁也可在 CI 中单独执行：

```powershell
Set-Location backend
python scripts/agent_eval_gate.py
```

## 测试与验证

后端测试会使用临时 `LIFESNAP_DATA_DIR`，不会修改开发者自己的本地工作区。请在仓库根目录执行：

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\test_runner.py all
.\backend\.venv\Scripts\python.exe .\backend\scripts\agent_eval_gate.py

npm --prefix frontend ci
npm --prefix frontend run check
npm --prefix frontend run test
```

测试层覆盖单元服务、HTTP 契约、真实 Uvicorn 工作流冒烟、离线 Agent/RAG 准入，以及 Playwright 桌面与移动端可用性检查。GitHub Actions 会在拉取请求和推送到 `main` 时运行这些校验。

## 仓库导航

| 路径 | 内容 |
| --- | --- |
| `frontend/` | 静态 Web 应用、运行时中英文切换、样式和 Playwright 冒烟测试 |
| `backend/app/api/` | FastAPI 路由层与 HTTP 契约 |
| `backend/app/services/` | 领域服务、Agent 运行时、RAG、OCR、任务、持久化和运维能力 |
| `backend/evaluations/` | 版本化 Agent 准入与 RAG 检索评测集 |
| `backend/tests/` | 单元测试与集成测试 |
| `docs/` | 架构、演示、业务评审、安全与升级参考 |
| `monitoring/` | Prometheus 抓取配置与起始告警规则 |
| `.github/workflows/` | 持续集成工作流 |

## 延伸文档

- [技术架构（English）](docs/architecture.md) / [技术架构](docs/architecture.zh-CN.md)
- [演示脚本（English）](docs/demo-runbook.md) / [演示脚本](docs/demo-runbook.zh-CN.md)
- [业务流程评审](docs/business-flow-review.md)
- [测试策略](docs/testing-strategy.md)
- [安全与访问边界](docs/security.md)
- [企业化升级参考](docs/enterprise-upgrade-reference.md)

## 当前边界

LifeSnap AI 有意保持为本地单工作区的参考实现。面向公网的多用户部署前，应迁移到托管关系型数据库，接入身份提供商和租户隔离，将密钥放入受管存储，迁移附件与向量索引服务，并通过网络策略保护指标与管理接口。详细路径见安全说明与企业化升级参考文档。
