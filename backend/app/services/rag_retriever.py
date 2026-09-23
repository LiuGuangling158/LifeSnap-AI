from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import httpx

from app.core.config import settings
from app.core.user_context import SYSTEM_OWNER_ID
from app.services.settings_store import settings_store
from app.services.sqlite_state_store import sqlite_state_store


@dataclass(frozen=True)
class RagDocument:
    source_id: str
    title: str
    content: str
    tags: tuple[str, ...]
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    source_id: str
    title: str
    content: str
    tags: tuple[str, ...]
    keywords: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True)
class RagSearchResult:
    chunk: RagChunk
    score: float
    lexical_score: float
    semantic_score: float | None
    retrieval_method: str


class HybridRagRetriever:
    """Hybrid BM25 and vector retrieval with a privacy-aware local fallback."""

    _namespace = "rag_embedding_cache"
    _chunk_size = 420

    def __init__(self) -> None:
        self._vectors = self._load_vectors()
        self._last_indexed_at: datetime | None = None
        self._last_error: str | None = None

    def search(self, query: str, documents: Iterable[RagDocument], *, limit: int = 3) -> list[RagSearchResult]:
        chunks = self.chunks(documents)
        if not chunks:
            return []
        lexical = self._bm25(query, chunks)
        semantic = self._semantic(query, chunks) if self.semantic_available() else {}
        weight = min(0.9, max(0.1, settings.rag_semantic_weight))
        results: list[RagSearchResult] = []
        for chunk in chunks:
            lexical_score = lexical.get(chunk.chunk_id, 0.0)
            semantic_score = semantic.get(chunk.chunk_id)
            score = lexical_score if semantic_score is None else (1 - weight) * lexical_score + weight * semantic_score
            if score > 0:
                results.append(RagSearchResult(
                    chunk=chunk,
                    score=min(1.0, round(score, 4)),
                    lexical_score=min(1.0, round(lexical_score, 4)),
                    semantic_score=round(semantic_score, 4) if semantic_score is not None else None,
                    retrieval_method="hybrid_bm25_vector" if semantic_score is not None else "bm25",
                ))
        return sorted(results, key=lambda item: item.score, reverse=True)[:max(0, limit)]

    def reindex(self, documents: Iterable[RagDocument]) -> dict[str, object]:
        chunks = self.chunks(documents)
        if self.semantic_available():
            self._index_missing(chunks)
            self._last_indexed_at = datetime.now(timezone.utc)
        return self.profile(chunks)

    def profile(self, chunks: list[RagChunk]) -> dict[str, object]:
        privacy = settings_store.get_privacy_settings()
        return {
            "strategy": "hybrid_bm25_vector" if self.semantic_available() else "bm25_local_fallback",
            "embedding_configured": settings.rag_embedding_configured,
            "embedding_ready": self.semantic_available(),
            "privacy_allows_external_embedding": bool(privacy.allow_ai_text_processing and not privacy.local_only_mode),
            "embedding_model": settings.rag_embedding_model,
            "chunk_count": len(chunks),
            "indexed_chunk_count": sum(chunk.fingerprint in self._vectors for chunk in chunks),
            "last_indexed_at": self._last_indexed_at,
            "last_error": self._last_error,
        }

    def semantic_available(self) -> bool:
        privacy = settings_store.get_privacy_settings()
        return bool(settings.rag_embedding_configured and privacy.allow_ai_text_processing and not privacy.local_only_mode)

    def chunks(self, documents: Iterable[RagDocument]) -> list[RagChunk]:
        chunks: list[RagChunk] = []
        for doc in documents:
            normalized = re.sub(r"\s+", " ", doc.content).strip()
            parts = self._split(normalized)
            for index, text in enumerate(parts):
                fingerprint = hashlib.sha256(
                    "\n".join((doc.source_id, doc.title, text, "|".join(doc.keywords))).encode("utf-8")
                ).hexdigest()
                chunks.append(RagChunk(
                    chunk_id=f"{doc.source_id}#{index + 1}", source_id=doc.source_id,
                    title=doc.title, content=text, tags=doc.tags, keywords=doc.keywords,
                    fingerprint=fingerprint,
                ))
        return chunks

    def _split(self, content: str) -> list[str]:
        if len(content) <= self._chunk_size:
            return [content] if content else []
        sentences = [item.strip() for item in re.split(r"(?<=[。！？.!?])\s*", content) if item.strip()]
        result, current = [], ""
        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > self._chunk_size:
                result.append(current)
                current = current[-60:] + " " + sentence
            else:
                current = f"{current} {sentence}".strip()
        return [*result, current] if current else result

    def _semantic(self, query: str, chunks: list[RagChunk]) -> dict[str, float]:
        query_vectors = self._embed([query])
        if not query_vectors:
            return {}
        self._index_missing(chunks)
        return {
            chunk.chunk_id: max(0.0, (self._cosine(query_vectors[0], vector) + 1) / 2)
            for chunk in chunks
            if (vector := self._vectors.get(chunk.fingerprint)) is not None
        }

    def _index_missing(self, chunks: list[RagChunk]) -> None:
        missing = [chunk for chunk in chunks if chunk.fingerprint not in self._vectors]
        if not missing:
            return
        vectors = self._embed([self._embed_text(chunk) for chunk in missing])
        if vectors is None or len(vectors) != len(missing):
            return
        self._vectors.update({chunk.fingerprint: vector for chunk, vector in zip(missing, vectors)})
        self._persist_vectors()

    def _embed(self, values: list[str]) -> list[list[float]] | None:
        try:
            response = httpx.post(
                str(settings.rag_embedding_endpoint),
                headers={"Authorization": f"Bearer {settings.rag_embedding_api_key}", "Content-Type": "application/json"},
                json={"model": settings.rag_embedding_model, "input": values},
                timeout=max(1.0, settings.rag_embedding_timeout_seconds),
            )
            response.raise_for_status()
            payload = response.json()
            rows = sorted(payload.get("data", []), key=lambda item: int(item.get("index", 0)))
            vectors = [[float(value) for value in row["embedding"]] for row in rows]
            if len(vectors) != len(values) or not all(vectors) or len({len(item) for item in vectors}) != 1:
                raise ValueError("incomplete embedding response")
            self._last_error = None
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError, OSError) as exc:
            self._last_error = f"embedding_unavailable:{type(exc).__name__}"
            return None

    def _bm25(self, query: str, chunks: list[RagChunk]) -> dict[str, float]:
        query_tokens = self._tokens(query)
        docs = [self._tokens(self._embed_text(chunk)) for chunk in chunks]
        if not query_tokens or not docs:
            return {}
        df: Counter[str] = Counter()
        for tokens in docs:
            df.update(set(tokens))
        average = sum(len(tokens) for tokens in docs) / len(docs)
        raw: dict[str, float] = {}
        for chunk, tokens in zip(chunks, docs):
            counts, score = Counter(tokens), 0.0
            for term in query_tokens:
                frequency = counts.get(term, 0)
                if frequency:
                    idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
                    score += idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * len(tokens) / max(1, average)))
            if any(keyword.casefold() in query.casefold() for keyword in chunk.keywords):
                score += 1.4
            raw[chunk.chunk_id] = score
        maximum = max(raw.values(), default=0.0)
        return {key: value / maximum if maximum else 0.0 for key, value in raw.items()}

    def _tokens(self, value: str) -> list[str]:
        ascii_terms = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", value.casefold())
        chinese_terms: list[str] = []
        for run in re.findall(r"[\u4e00-\u9fff]+", value):
            chinese_terms.extend(run)
            chinese_terms.extend(run[index:index + 2] for index in range(len(run) - 1))
        return ascii_terms + chinese_terms

    def _embed_text(self, chunk: RagChunk) -> str:
        return "\n".join((chunk.title, " ".join(chunk.tags), " ".join(chunk.keywords), chunk.content))

    def _load_vectors(self) -> dict[str, list[float]]:
        payload = sqlite_state_store.load_json(self._namespace, settings.local_rag_embedding_cache_path, owner_id=SYSTEM_OWNER_ID)
        if not isinstance(payload, dict) or payload.get("model") != settings.rag_embedding_model:
            return {}
        return {
            str(key): [float(value) for value in vector]
            for key, vector in payload.get("vectors", {}).items()
            if isinstance(vector, list) and vector
        }

    def _persist_vectors(self) -> None:
        sqlite_state_store.save_json(
            self._namespace,
            {"model": settings.rag_embedding_model, "updated_at": datetime.now(timezone.utc).isoformat(), "vectors": self._vectors},
            owner_id=SYSTEM_OWNER_ID,
        )

    def _cosine(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            return 0.0
        denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
        return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


hybrid_rag_retriever = HybridRagRetriever()
