from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from app.core.config import settings
from app.core.user_context import SYSTEM_OWNER_ID
from app.schemas.agent_runtime import (
    AgentKnowledgeBaseResponse,
    AgentKnowledgeDocument,
    AgentKnowledgeDocumentInput,
    AgentKnowledgeHit,
    AgentRagProfile,
    AgentKnowledgeSource,
    AgentKnowledgeVersionSummary,
)
from app.services.rag_retriever import RagDocument, hybrid_rag_retriever
from app.services.sqlite_state_store import sqlite_state_store


@dataclass(frozen=True)
class KnowledgeDocument:
    source_id: str
    title: str
    content: str
    tags: tuple[str, ...]
    keywords: tuple[str, ...]
    source: str = "builtin"
    enabled: bool = True
    updated_at: datetime | None = None


@dataclass(frozen=True)
class KnowledgeVersion:
    version_id: str
    action: str
    created_at: datetime
    documents: tuple[KnowledgeDocument, ...]


class AgentKnowledgeBase:
    _max_versions = 20
    _builtin_documents = (
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
            source_id="bill_analysis_policy",
            title="账单分析规则",
            content=(
                "当用户询问本月或某月花了多少、收入多少、分类占比、商户排行或消费分析时，"
                "Agent 应先读取本地账单统计，再基于确定性金额生成解释，不能让模型编造数字。"
                "趋势、环比、预算、超支和单日最高支出也必须由本地统计计算后再解释。"
                "预算与消费问题应返回折线图、预算进度、分类分布等可视化数据，再给出 AI 评估。"
            ),
            tags=("bill", "analysis", "function_calling"),
            keywords=("账单分析", "消费分析", "统计", "花了多少", "支出多少", "收入多少", "占比", "排行", "最多", "趋势", "环比", "预算", "折线图", "可视化", "评估"),
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
                "账单分析、日记整理、候选更新、候选确认和候选丢弃。写操作继续受确认和幂等保护。"
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

    def __init__(self) -> None:
        self._admin_documents = self._load_admin_documents()
        self._versions = self._load_versions()

    def search(self, query: str, limit: int = 3) -> list[AgentKnowledgeHit]:
        query_text = query.strip()
        if not query_text:
            return []

        results = hybrid_rag_retriever.search(
            query_text,
            self._rag_documents(),
            limit=limit,
        )
        return [
            AgentKnowledgeHit(
                source_id=result.chunk.source_id,
                title=result.chunk.title,
                snippet=result.chunk.content[:240],
                score=result.score,
                tags=list(result.chunk.tags),
                chunk_id=result.chunk.chunk_id,
                retrieval_method=result.retrieval_method,
                lexical_score=result.lexical_score,
                semantic_score=result.semantic_score,
            )
            for result in results
        ]

    def reindex(self) -> AgentRagProfile:
        return AgentRagProfile.model_validate(
            hybrid_rag_retriever.reindex(self._rag_documents())
        )

    def response(self) -> AgentKnowledgeBaseResponse:
        active_documents = self._documents()
        documents = [
            self._to_schema(document)
            for document in self._documents(include_disabled=True)
        ]
        retrieval = AgentRagProfile.model_validate(
            hybrid_rag_retriever.profile(hybrid_rag_retriever.chunks(self._rag_documents()))
        )
        return AgentKnowledgeBaseResponse(
            generated_at=datetime.now(timezone.utc),
            total=len(documents),
            builtin_count=len(self._builtin_documents),
            admin_count=len(self._admin_documents),
            active_count=len(active_documents),
            documents=documents,
            versions=self._version_summaries(),
            retrieval=retrieval,
        )
    def replace_admin_documents(
        self,
        documents: Iterable[AgentKnowledgeDocumentInput],
    ) -> AgentKnowledgeBaseResponse:
        now = datetime.now(timezone.utc)
        by_id: dict[str, KnowledgeDocument] = {}
        order: list[str] = []
        for document in documents:
            normalized = self._normalize_input(document, updated_at=now)
            if normalized.source_id not in by_id:
                order.append(normalized.source_id)
            by_id[normalized.source_id] = normalized
        self._admin_documents = tuple(by_id[source_id] for source_id in order)
        self._record_version("replace")
        self._persist_admin_documents()
        return self.response()

    def reset_admin_documents(self) -> AgentKnowledgeBaseResponse:
        self._admin_documents = ()
        self._record_version("reset")
        self._persist_admin_documents()
        return self.response()

    def rollback_admin_documents(self, version_id: str) -> AgentKnowledgeBaseResponse:
        version = next((item for item in self._versions if item.version_id == version_id), None)
        if version is None:
            raise ValueError("Knowledge version not found")
        now = datetime.now(timezone.utc)
        self._admin_documents = tuple(
            KnowledgeDocument(
                source_id=document.source_id,
                title=document.title,
                content=document.content,
                tags=document.tags,
                keywords=document.keywords,
                source="admin",
                enabled=document.enabled,
                updated_at=now,
            )
            for document in version.documents
        )
        self._record_version("rollback")
        self._persist_admin_documents()
        return self.response()

    def latest_version_id(self) -> str | None:
        return self._versions[0].version_id if self._versions else None

    def sources(self) -> list[AgentKnowledgeSource]:
        groups: dict[str, list[KnowledgeDocument]] = {}
        for document in self._documents():
            group = document.tags[0] if document.tags else "agent"
            groups.setdefault(group, []).append(document)

        labels = {
            "agent": "Agent 工作流知识",
            "bill": "账单业务知识",
            "privacy": "隐私与外部服务知识",
            "task": "待办提醒知识",
            "diary": "日记整理知识",
            "admin": "管理员知识",
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
        return len(self._documents())

    def _rag_documents(self) -> list[RagDocument]:
        return [
            RagDocument(
                source_id=document.source_id,
                title=document.title,
                content=document.content,
                tags=document.tags,
                keywords=document.keywords,
            )
            for document in self._documents()
        ]
    def _documents(self, *, include_disabled: bool = False) -> list[KnowledgeDocument]:
        by_id: dict[str, KnowledgeDocument] = {}
        order: list[str] = []
        for document in self._builtin_documents:
            by_id[document.source_id] = document
            order.append(document.source_id)

        for document in self._admin_documents:
            if document.source_id not in by_id:
                order.append(document.source_id)
            if include_disabled or document.enabled:
                by_id[document.source_id] = document
            else:
                by_id.pop(document.source_id, None)

        return [by_id[source_id] for source_id in order if source_id in by_id]

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

    def _load_admin_documents(self) -> tuple[KnowledgeDocument, ...]:
        raw_payload = sqlite_state_store.load_json(
            "agent_knowledge",
            settings.local_agent_knowledge_path,
            owner_id=SYSTEM_OWNER_ID,
        )
        if raw_payload is None:
            return ()
        try:
            raw_documents = raw_payload.get("documents", raw_payload) if isinstance(raw_payload, dict) else raw_payload
            if not isinstance(raw_documents, list):
                return ()
            loaded: list[KnowledgeDocument] = []
            for raw_document in raw_documents:
                if not isinstance(raw_document, dict):
                    continue
                payload = AgentKnowledgeDocumentInput.model_validate(raw_document)
                loaded.append(
                    self._normalize_input(
                        payload,
                        updated_at=self._parse_datetime(raw_document.get("updated_at")),
                    )
                )
            return tuple(loaded)
        except (ValueError, TypeError):
            return ()

    def _load_versions(self) -> tuple[KnowledgeVersion, ...]:
        raw_payload = sqlite_state_store.load_json(
            "agent_knowledge",
            settings.local_agent_knowledge_path,
            owner_id=SYSTEM_OWNER_ID,
        )
        if raw_payload is None:
            return ()
        try:
            if not isinstance(raw_payload, dict):
                return ()
            raw_versions = raw_payload.get("versions", [])
            if not isinstance(raw_versions, list):
                return ()
            versions: list[KnowledgeVersion] = []
            for raw_version in raw_versions:
                if not isinstance(raw_version, dict):
                    continue
                version_id = str(raw_version.get("version_id") or "").strip()
                action = str(raw_version.get("action") or "replace").strip()[:40]
                created_at = self._parse_datetime(raw_version.get("created_at"))
                raw_documents = raw_version.get("documents", [])
                if not version_id or not created_at or not isinstance(raw_documents, list):
                    continue
                documents: list[KnowledgeDocument] = []
                for raw_document in raw_documents:
                    if not isinstance(raw_document, dict):
                        continue
                    payload = AgentKnowledgeDocumentInput.model_validate(raw_document)
                    documents.append(
                        self._normalize_input(
                            payload,
                            updated_at=self._parse_datetime(raw_document.get("updated_at")),
                        )
                    )
                versions.append(
                    KnowledgeVersion(
                        version_id=version_id,
                        action=action or "replace",
                        created_at=created_at,
                        documents=tuple(documents),
                    )
                )
            return tuple(versions[: self._max_versions])
        except (ValueError, TypeError):
            return ()

    def _persist_admin_documents(self) -> None:
        sqlite_state_store.save_json(
            "agent_knowledge",
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "documents": [
                    self._to_schema(document).model_dump(mode="json")
                    for document in self._admin_documents
                ],
                "versions": [self._version_to_payload(version) for version in self._versions],
            },
            owner_id=SYSTEM_OWNER_ID,
        )

    def _record_version(self, action: str) -> None:
        now = datetime.now(timezone.utc)
        version = KnowledgeVersion(
            version_id=f"rag-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            action=action,
            created_at=now,
            documents=self._admin_documents,
        )
        self._versions = (version, *self._versions)[: self._max_versions]

    def _version_summaries(self) -> list[AgentKnowledgeVersionSummary]:
        return [
            AgentKnowledgeVersionSummary(
                version_id=version.version_id,
                action=version.action,
                created_at=version.created_at,
                admin_count=len(version.documents),
                active_count=sum(1 for document in version.documents if document.enabled),
                document_titles=[document.title for document in version.documents[:8]],
            )
            for version in self._versions
        ]

    def _version_to_payload(self, version: KnowledgeVersion) -> dict[str, object]:
        return {
            "version_id": version.version_id,
            "action": version.action,
            "created_at": version.created_at.isoformat(),
            "documents": [
                self._to_schema(document).model_dump(mode="json")
                for document in version.documents
            ],
        }

    def _normalize_input(
        self,
        payload: AgentKnowledgeDocumentInput,
        *,
        updated_at: datetime | None,
    ) -> KnowledgeDocument:
        title = payload.title.strip()
        content = payload.content.strip()
        tags = self._normalize_strings(payload.tags, limit=8, max_length=40) or ("admin",)
        keywords = self._normalize_strings(payload.keywords, limit=24, max_length=60)
        if not keywords:
            keywords = self._fallback_keywords(title, tags)
        return KnowledgeDocument(
            source_id=payload.source_id.strip(),
            title=title,
            content=content,
            tags=tags,
            keywords=keywords,
            source="admin",
            enabled=payload.enabled,
            updated_at=updated_at or datetime.now(timezone.utc),
        )

    def _normalize_strings(
        self,
        values: Iterable[str],
        *,
        limit: int,
        max_length: int,
    ) -> tuple[str, ...]:
        normalized: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if not text or len(text) > max_length or text in normalized:
                continue
            normalized.append(text)
            if len(normalized) >= limit:
                break
        return tuple(normalized)

    def _fallback_keywords(self, title: str, tags: tuple[str, ...]) -> tuple[str, ...]:
        keywords = [title, *tags]
        return tuple(value for value in keywords if value)[:24]

    def _parse_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _to_schema(self, document: KnowledgeDocument) -> AgentKnowledgeDocument:
        return AgentKnowledgeDocument(
            source_id=document.source_id,
            title=document.title,
            content=document.content,
            tags=list(document.tags),
            keywords=list(document.keywords),
            source=document.source,
            enabled=document.enabled,
            updated_at=document.updated_at,
        )


agent_knowledge_base = AgentKnowledgeBase()
