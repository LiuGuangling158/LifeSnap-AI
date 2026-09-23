from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.rag_retriever import HybridRagRetriever, RagDocument


class _EmbeddingResponse:
    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = vectors

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "data": [
                {"index": index, "embedding": vector}
                for index, vector in enumerate(self._vectors)
            ]
        }


class HybridRagRetrieverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = [
            RagDocument(
                source_id="coffee",
                title="饮品分类规则",
                content="奶茶、咖啡和果汁默认归到餐饮分类。",
                tags=("bill", "category"),
                keywords=("奶茶", "咖啡", "饮品"),
            ),
            RagDocument(
                source_id="transport",
                title="交通分类规则",
                content="地铁、公交和打车默认归到交通分类。",
                tags=("bill", "category"),
                keywords=("地铁", "打车", "交通"),
            ),
        ]

    @patch("app.services.rag_retriever.settings_store.get_privacy_settings")
    def test_local_bm25_fallback_returns_chunk_metadata(self, privacy_settings) -> None:
        privacy_settings.return_value = SimpleNamespace(
            allow_ai_text_processing=True,
            local_only_mode=True,
        )
        results = HybridRagRetriever().search("奶茶应该怎么分类", self.documents)

        self.assertEqual(results[0].chunk.source_id, "coffee")
        self.assertEqual(results[0].retrieval_method, "bm25")
        self.assertIsNone(results[0].semantic_score)

    @patch("app.services.rag_retriever.httpx.post")
    @patch("app.services.rag_retriever.settings_store.get_privacy_settings")
    @patch("app.services.rag_retriever.settings")
    def test_embedding_enabled_uses_hybrid_retrieval(
        self,
        runtime_settings,
        privacy_settings,
        post,
    ) -> None:
        runtime_settings.rag_embedding_configured = True
        runtime_settings.rag_embedding_endpoint = "https://embedding.example/v1/embeddings"
        runtime_settings.rag_embedding_api_key = "test-key"
        runtime_settings.rag_embedding_model = "test-model"
        runtime_settings.rag_embedding_timeout_seconds = 3.0
        runtime_settings.rag_semantic_weight = 0.65
        privacy_settings.return_value = SimpleNamespace(
            allow_ai_text_processing=True,
            local_only_mode=False,
        )

        def embedding_response(*_args, json, **_kwargs):
            values = json["input"]
            vectors = [
                [1.0, 0.0] if "奶茶" in value or "咖啡" in value or "饮品" in value else [0.0, 1.0]
                for value in values
            ]
            return _EmbeddingResponse(vectors)

        post.side_effect = embedding_response
        retriever = HybridRagRetriever()
        results = retriever.search("饮品开销如何分类", self.documents)

        self.assertEqual(results[0].chunk.source_id, "coffee")
        self.assertEqual(results[0].retrieval_method, "hybrid_bm25_vector")
        self.assertIsNotNone(results[0].semantic_score)
        self.assertGreaterEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
