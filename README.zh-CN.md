# LifeSnap AI

English: [README.md](README.md) | 简体中文

![LifeSnap AI 概念主视觉](docs/assets/lifesnap-ai-demo-hero.png)

LifeSnap AI 是一个本地优先的个人财务工作台，覆盖账单记录、消费分析和 AI
助手协同操作。它的目标不是展示一个只能聊天的原型，而是提供一套可审核、可追溯的
AI 财务工作流参考实现。

> 上图为使用 ChatGPT Image 2 生成的演示概念视觉，并非应用真实截图。

## 项目能力

- 基于 SQLite 持久化账单、待办、日记、附件和仪表盘数据。
- 支持图片账单识别，并在保存前提供核对和修改步骤。
- Agent 运行时具备意图路由、RAG 检索、函数调用和可追踪的工具执行过程。
- 支持人工纠错反馈与可重复运行的 AI 质量评测。
- 提供月度报告中心、分类预算规则与确定性异常消费提醒。
- 提供面向生产的请求日志、Prometheus 指标、告警规则、诊断信息和分层测试。
- 默认采用本地单用户模式；RAG 知识库管理使用独立的短期管理员会话保护。

## 快速启动

1. 将 .env.example 复制为 .env，只填写要启用的模型服务配置。未配置外部模型时，
   应用仍可使用本地降级能力。
2. 创建并激活虚拟环境：

    cd backend
    python -m venv .venv
    .\\.venv\\Scripts\\Activate.ps1
    pip install -r requirements.txt

3. 启动应用：

    uvicorn app.main:app --host 127.0.0.1 --port 8023

在浏览器打开 http://127.0.0.1:8023。

## 文档

- [技术架构](docs/architecture.zh-CN.md)：运行边界、数据流和 AI 执行模型。
- [演示脚本](docs/demo-runbook.zh-CN.md)：可复现的产品演示流程。
- [业务流程评审](docs/business-flow-review.md)：用户路径和产品决策。
- [企业化升级参考](docs/enterprise-upgrade-reference.md)：交付路线和成熟度标准。
- [测试策略](docs/testing-strategy.md)：单元、集成、工作流和浏览器测试分层。
- [安全说明](docs/security.md)：隐私、密钥和生产部署边界。

## 目录结构

| 路径 | 用途 |
| --- | --- |
| frontend | 静态 Web 客户端、国际化与 Playwright 可用性测试 |
| backend | FastAPI 接口、Agent 服务、持久化与后端测试 |
| docs | 架构、操作指南、评审材料和演示资产 |
| monitoring | Prometheus 抓取配置和告警规则 |
| .github | 持续集成工作流 |

## 验证

本地测试命令见 [测试策略](docs/testing-strategy.md)。CI 会验证后端单元、集成和
工作流测试，以及前端静态检查和浏览器可用性测试。
