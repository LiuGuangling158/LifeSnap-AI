from __future__ import annotations

import hashlib
import math
import re
import threading
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
    """Persistent, chunk-aware hybrid retrieval with a safe local fallback."""

    _namespace = "rag_embedding_cache"
    _cache_schema_version = 2
    _chunk_size = 420
    _chunk_overlap = 60
    _embedding_batch_size = 16

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._vectors, self._last_indexed_at = self._load_cache()
        self._last_error: str | None = None

    def search(
        self,
        query: str,
        documents: Iterable[RagDocument],
        *,
        limit: int = 3,
    ) -> list[RagSearchResult]:
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
            score = (
                lexical_score
                if semantic_score is None
                else (1 - weight) * lexical_score + weight * semantic_score
            )
            if score <= 0:
                continue
            results.append(
                RagSearchResult(
                    chunk=chunk,
                    score=min(1.0, round(score, 4)),
                    lexical_score=min(1.0, round(lexical_score, 4)),
                    semantic_score=round(semantic_score, 4)
                    if semantic_score is not None
                    else None,
                    retrieval_method=(
                        "hybrid_bm25_vector"
                        if semantic_score is not None
                        else "bm25"
                    ),
                )
            )
        return self._select_diverse(results, limit)

    def reindex(self, documents: Iterable[RagDocument]) -> dict[str, object]:
        chunks = self.chunks(documents)
        if self.semantic_available():
            self._synchronize_index(chunks)
        return self.profile(chunks)

    def profile(self, chunks: list[RagChunk]) -> dict[str, object]:
        privacy = settings_store.get_privacy_settings()
        active_fingerprints = {chunk.fingerprint for chunk in chunks}
        return {
            "strategy": (
                "hybrid_bm25_vector"
                if self.semantic_available()
                else "bm25_local_fallback"
            ),
            "embedding_configured": settings.rag_embedding_configured,
            "embedding_ready": self.semantic_available(),
            "privacy_allows_external_embedding": bool(
                privacy.allow_ai_text_processing and not privacy.local_only_mode
            ),
            "embedding_model": settings.rag_embedding_model,
            "chunk_count": len(chunks),
            "indexed_chunk_count": sum(
                fingerprint in self._vectors for fingerprint in active_fingerprints
            ),
            "last_indexed_at": self._last_indexed_at,
            "last_error": self._last_error,
        }

    def semantic_available(self) -> bool:
        privacy = settings_store.get_privacy_settings()
        return bool(
            settings.rag_embedding_configured
            and privacy.allow_ai_text_processing
            and not privacy.local_only_mode
        )

    def chunks(self, documents: Iterable[RagDocument]) -> list[RagChunk]:
        chunks: list[RagChunk] = []
        for document in documents:
            for index, content in enumerate(self._split(document.content)):
                fingerprint = hashlib.sha256(
                    "\n".join(
                        (
                            document.source_id,
                            document.title,
                            content,
                            "|".join(document.keywords),
                        )
                    ).encode("utf-8")
                ).hexdigest()
                chunks.append(
                    RagChunk(
                        chunk_id=f"{document.source_id}#{index + 1}",
                        source_id=document.source_id,
                        title=document.title,
                        content=content,
                        tags=document.tags,
                        keywords=document.keywords,
                        fingerprint=fingerprint,
                    )
                )
        return chunks

    def _split(self, content: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", content).strip()
        if not normalized:
            return []
        if len(normalized) <= self._chunk_size:
            return [normalized]

        sentences = [
            item.strip()
            for item in re.split(r"(?<=[。！？.!?])\s*", normalized)
            if item.strip()
        ]
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > self._chunk_size:
                chunks.append(current)
                current = current[-self._chunk_overlap :] + " " + sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current)
        return chunks

    def _semantic(self, query: str, chunks: list[RagChunk]) -> dict[str, float]:
        query_vectors = self._embed([query])
        if not query_vectors or not self._synchronize_index(chunks):
            return {}
        query_vector = query_vectors[0]
        return {
            chunk.chunk_id: max(0.0, self._cosine(query_vector, vector))
            for chunk in chunks
            if (vector := self._vectors.get(chunk.fingerprint)) is not None
        }

    def _synchronize_index(self, chunks: list[RagChunk]) -> bool:
        if not self.semantic_available():
            return False
        with self._lock:
            active_fingerprints = {chunk.fingerprint for chunk in chunks}
            stale = set(self._vectors) - active_fingerprints
            for fingerprint in stale:
                self._vectors.pop(fingerprint, None)
            missing = [
                chunk for chunk in chunks if chunk.fingerprint not in self._vectors
            ]

        if missing:
            for batch in self._batches(missing, self._embedding_batch_size):
                vectors = self._embed([self._embed_text(chunk) for chunk in batch])
                if vectors is None or len(vectors) != len(batch):
                    return False
                with self._lock:
                    self._vectors.update(
                        {
                            chunk.fingerprint: vector
                            for chunk, vector in zip(batch, vectors)
                        }
                    )

        with self._lock:
            self._last_indexed_at = datetime.now(timezone.utc)
            self._persist_cache()
        return True

    def _embed(self, values: list[str]) -> list[list[float]] | None:
        if not values:
            return []
        try:
            response = httpx.post(
                str(settings.rag_embedding_endpoint),
                headers={
                    "Authorization": f"Bearer {settings.rag_embedding_api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": settings.rag_embedding_model, "input": values},
                timeout=max(1.0, settings.rag_embedding_timeout_seconds),
            )
            response.raise_for_status()
            payload = response.json()
            rows = sorted(
                payload.get("data", []),
                key=lambda item: int(item.get("index", 0)),
            )
            vectors = [
                [float(value) for value in row["embedding"]]
                for row in rows
            ]
            if (
                len(vectors) != len(values)
                or not all(vectors)
                or len({len(vector) for vector in vectors}) != 1
            ):
                raise ValueError("incomplete embedding response")
            self._last_error = None
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError, OSError) as exc:
            self._last_error = f"embedding_unavailable:{type(exc).__name__}"
            return None

    def _bm25(self, query: str, chunks: list[RagChunk]) -> dict[str, float]:
        query_tokens = self._tokens(query)
        documents = [self._tokens(self._embed_text(chunk)) for chunk in chunks]
        if not query_tokens or not documents:
            return {}

        document_frequencies: Counter[str] = Counter()
        for tokens in documents:
            document_frequencies.update(set(tokens))
        average_length = sum(len(tokens) for tokens in documents) / len(documents)

        raw_scores: dict[str, float] = {}
        for chunk, tokens in zip(chunks, documents):
            frequencies = Counter(tokens)
            score = 0.0
            for term in query_tokens:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                idf = math.log(
                    1
                    + (len(documents) - document_frequencies[term] + 0.5)
                    / (document_frequencies[term] + 0.5)
                )
                score += idf * frequency * 2.2 / (
                    frequency
                    + 1.2
                    * (0.25 + 0.75 * len(tokens) / max(1, average_length))
                )
            if any(keyword.casefold() in query.casefold() for keyword in chunk.keywords):
                score += 1.4
            raw_scores[chunk.chunk_id] = score

        maximum = max(raw_scores.values(), default=0.0)
        return {
            key: value / maximum if maximum else 0.0
            for key, value in raw_scores.items()
        }

    def _select_diverse(
        self,
        results: list[RagSearchResult],
        limit: int,
    ) -> list[RagSearchResult]:
        ranked = sorted(results, key=lambda item: item.score, reverse=True)
        selected: list[RagSearchResult] = []
        seen_sources: set[str] = set()
        for result in ranked:
            if result.chunk.source_id in seen_sources:
                continue
            selected.append(result)
            seen_sources.add(result.chunk.source_id)
            if len(selected) >= limit:
                return selected
        for result in ranked:
            if result in selected:
                continue
            selected.append(result)
            if len(selected) >= limit:
                break
        return selected

    def _tokens(self, value: str) -> list[str]:
        ascii_terms = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", value.casefold())
        chinese_terms: list[str] = []
        for run in re.findall(r"[\u4e00-\u9fff]+", value):
            chinese_terms.extend(run)
            chinese_terms.extend(
                run[index : index + 2] for index in range(len(run) - 1)
            )
        return ascii_terms + chinese_terms

    def _embed_text(self, chunk: RagChunk) -> str:
        return "\n".join(
            (chunk.title, " ".join(chunk.tags), " ".join(chunk.keywords), chunk.content)
        )

    def _load_cache(self) -> tuple[dict[str, list[float]], datetime | None]:
        payload = sqlite_state_store.load_json(
            self._namespace,
            settings.local_rag_embedding_cache_path,
            owner_id=SYSTEM_OWNER_ID,
        )
        if not isinstance(payload, dict):
            return {}, None
        if payload.get("schema_version") != self._cache_schema_version:
            return {}, None
        if payload.get("embedding_config") != self._embedding_config_fingerprint():
            return {}, None
        vectors = payload.get("vectors")
        if not isinstance(vectors, dict):
            return {}, None
        indexed_at = self._parse_datetime(payload.get("last_indexed_at"))
        return (
            {
                str(key): [float(value) for value in vector]
                for key, vector in vectors.items()
                if isinstance(vector, list) and vector
            },
            indexed_at,
        )

    def _persist_cache(self) -> None:
        sqlite_state_store.save_json(
            self._namespace,
            {
                "schema_version": self._cache_schema_version,
                "embedding_config": self._embedding_config_fingerprint(),
                "last_indexed_at": (
                    self._last_indexed_at.isoformat()
                    if self._last_indexed_at
                    else None
                ),
                "vectors": self._vectors,
            },
            owner_id=SYSTEM_OWNER_ID,
        )

    def _embedding_config_fingerprint(self) -> str:
        value = "|".join(
            (
                str(settings.rag_embedding_endpoint or ""),
                str(settings.rag_embedding_model or ""),
            )
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _parse_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _batches(self, values: list[RagChunk], size: int) -> Iterable[list[RagChunk]]:
        for index in range(0, len(values), size):
            yield values[index : index + size]

    def _cosine(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            return 0.0
        denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
            sum(value * value for value in right)
        )
        if not denominator:
            return 0.0
        return sum(a * b for a, b in zip(left, right)) / denominator


hybrid_rag_retriever = HybridRagRetriever()
