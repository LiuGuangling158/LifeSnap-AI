from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.agent_runtime import AgentKnowledgeHit, AgentKnowledgeSource


@dataclass(frozen=True)
class KnowledgeDocument:
    source_id: str
    title: str
    content: str
    tags: tuple[str, ...]
    keywords: tuple[str, ...]


class AgentKnowledgeBase:
    _documents = (
        KnowledgeDocument(
            source_id="bill_required_fields",
            title="账单必填规则",
            content=(
                "账单保存只强制要求金额和收支类型。商家/用途、分类、支付方式、"
                "记账时间和备注都可以选填；空商家保存为 null，展示为未填写。"
            ),
            tags=("bill", "validation"),
            keywords=("账单", "金额", "收支类型", "必填", "选填", "商家", "用途"),
        ),
        KnowledgeDocument(
            source_id="bill_category_policy",
            title="花销分类知识",
            content=(
                "分类优先遵循用户明确说出的分类或类别。没有明确分类时，按商家、物品和场景关键词"
                "推断餐饮、交通、购物、日用、医疗、娱乐、学习和住房等分类；居住会归一为住房。"
            ),
            tags=("bill", "category", "rag"),
            keywords=(
                "分类",
                "类别",
                "花销",
                "餐饮",
                "交通",
                "购物",
                "日用",
                "医疗",
                "娱乐",
                "学习",
                "住房",
                "居住",
                "咖啡",
                "外卖",
                "打车",
                "高铁",
                "淘宝",
                "超市",
                "买药",
                "电影",
                "课程",
                "房租",
            ),
        ),
        KnowledgeDocument(
            source_id="candidate_confirmation_policy",
            title="候选确认机制",
            content=(
                "Agent 不直接写入正式账单、待办或日记，而是先创建候选记录。用户确认后才保存，"
                "也可以在聊天里继续补充或丢弃候选。"
            ),
            tags=("agent", "safety"),
            keywords=("候选", "确认", "保存", "丢弃", "修改", "安全", "Agent"),
        ),
        KnowledgeDocument(
            source_id="function_calling_policy",
            title="函数调用工具链",
            content=(
                "Agent 会根据意图选择内部函数工具：知识库检索、账单解析、花销分类、待办解析、"
                "日记整理、候选更新、候选确认和候选丢弃。写操作继续受确认和幂等保护。"
            ),
            tags=("agent", "function_calling"),
            keywords=("function calling", "函数调用", "工具调用", "工具", "解析", "确认", "幂等"),
        ),
        KnowledgeDocument(
            source_id="fine_tuning_policy",
            title="大模型微调策略",
            content=(
                "项目支持配置微调后的 OpenAI-compatible 模型 ID，并优先使用该模型进行意图识别和候选抽取。"
                "本地数据可导出为监督微调样本，但训练动作需要在外部模型平台完成。"
            ),
            tags=("agent", "fine_tuning"),
            keywords=("微调", "fine-tuning", "fine tuning", "训练", "模型", "大模型", "LLM"),
        ),
        KnowledgeDocument(
            source_id="privacy_policy",
            title="隐私与外部模型",
            content=(
                "隐私设置默认本地优先。local_only_mode 开启时不会调用外部 OCR 或大模型；"
                "允许外部处理后，才会访问配置的 OCR、解析服务或 OpenAI-compatible LLM。"
            ),
            tags=("privacy", "llm"),
            keywords=("隐私", "本地", "外部", "OCR", "大模型", "local_only"),
        ),
        KnowledgeDocument(
            source_id="task_policy",
            title="待办和提醒规则",
            content=(
                "普通待办至少需要标题；提醒还需要提醒时间。Agent 会先生成待确认事项，用户确认后保存。"
            ),
            tags=("task", "reminder"),
            keywords=("待办", "提醒", "任务", "标题", "提醒时间", "截止时间"),
        ),
        KnowledgeDocument(
            source_id="diary_policy",
            title="日记整理规则",
            content=(
                "日记候选会整理日期、标题、正文、心情、天气和标签。心情整理问题不会直接创建记录。"
            ),
            tags=("diary",),
            keywords=("日记", "心情", "天气", "标签", "正文", "记录"),
        ),
    )

    def search(self, query: str, limit: int = 3) -> list[AgentKnowledgeHit]:
        query_text = query.strip()
        if not query_text:
            return []

        query_terms = self._terms(query_text)
        scored: list[tuple[float, KnowledgeDocument, tuple[str, ...]]] = []
        for document in self._documents:
            score, matched = self._score_document(query_text, query_terms, document)
            if score <= 0:
                continue
            scored.append((score, document, matched))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            AgentKnowledgeHit(
                source_id=document.source_id,
                title=document.title,
                snippet=document.content[:240],
                score=min(1.0, round(score, 2)),
                tags=list(document.tags),
            )
            for score, document, _ in scored[: max(0, limit)]
        ]

    def sources(self) -> list[AgentKnowledgeSource]:
        groups: dict[str, list[KnowledgeDocument]] = {}
        for document in self._documents:
            group = document.tags[0] if document.tags else "agent"
            groups.setdefault(group, []).append(document)

        labels = {
            "agent": "Agent 工作流知识",
            "bill": "账单业务知识",
            "privacy": "隐私与外部服务知识",
            "task": "待办提醒知识",
            "diary": "日记整理知识",
        }
        return [
            AgentKnowledgeSource(
                source_id=source_id,
                title=labels.get(source_id, source_id),
                description="、".join(document.title for document in documents[:3]),
                document_count=len(documents),
                tags=sorted({tag for document in documents for tag in document.tags}),
            )
            for source_id, documents in groups.items()
        ]

    def document_count(self) -> int:
        return len(self._documents)

    def _score_document(
        self,
        query_text: str,
        query_terms: set[str],
        document: KnowledgeDocument,
    ) -> tuple[float, tuple[str, ...]]:
        content = f"{document.title} {document.content}".casefold()
        matched: list[str] = []
        score = 0.0

        for keyword in document.keywords:
            normalized_keyword = keyword.casefold()
            if normalized_keyword and normalized_keyword in query_text.casefold():
                score += 0.42 + min(len(keyword), 6) * 0.04
                matched.append(keyword)

        for term in query_terms:
            if term in content:
                score += 0.1
        return score, tuple(matched)

    def _terms(self, query: str) -> set[str]:
        ascii_terms = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", query.casefold()))
        chinese_terms = {char for char in query if "\u4e00" <= char <= "\u9fff"}
        return ascii_terms | chinese_terms


agent_knowledge_base = AgentKnowledgeBase()
