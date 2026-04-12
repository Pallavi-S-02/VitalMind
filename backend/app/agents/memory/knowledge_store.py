"""
knowledge_store.py — Pinecone-backed semantic search over the medical knowledge base.

Wraps all Pinecone operations so the rest of the codebase never imports
pinecone directly. Handles embedding generation via OpenAI and provides
a clean search() interface consumed by agent tool nodes.

Index: PINECONE_INDEX_NAME  (default: "vitalmind-kb")
Namespace: Configurable per query (e.g. "symptoms", "drugs", "reports")
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "models/text-embedding-004"
_EMBEDDING_DIMENSION = 768  # text-embedding-004 output dimension
_DEFAULT_NAMESPACE = "general"
_TOP_K_DEFAULT = 5


class KnowledgeStore:
    """
    Semantic search over the VitalMind medical knowledge base stored in Pinecone.

    Usage
    -----
        store = KnowledgeStore()
        results = store.search("chest pain shortness of breath", namespace="symptoms", top_k=3)
        for r in results:
            print(r["text"], r["score"])
    """

    def __init__(self) -> None:
        api_key = os.getenv("PINECONE_API_KEY", "")
        self._index_name = os.getenv("PINECONE_INDEX_NAME", "vitalmind-kb")

        # Embeddings client (Google text-embedding-004)
        self._embedder = GoogleGenerativeAIEmbeddings(
            model=_EMBEDDING_MODEL,
            google_api_key=__import__("os").getenv("GOOGLE_API_KEY"),
        )

        # Pinecone client (v3 SDK)
        if not api_key:
            logger.warning("PINECONE_API_KEY not set — KnowledgeStore will be non-functional.")
            self._index = None
            return

        try:
            pc = Pinecone(api_key=api_key)
            # Create index if it doesn't exist yet
            existing = [idx.name for idx in pc.list_indexes()]
            if self._index_name not in existing:
                logger.info("Creating Pinecone index '%s'...", self._index_name)
                pc.create_index(
                    name=self._index_name,
                    dimension=_EMBEDDING_DIMENSION,  # text-embedding-004: 768
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud=os.getenv("PINECONE_CLOUD", "aws"),
                        region=os.getenv("PINECONE_REGION", "us-east-1"),
                    ),
                )
            self._index = pc.Index(self._index_name)
            logger.info("KnowledgeStore connected to Pinecone index '%s'.", self._index_name)
        except Exception as exc:
            logger.error("KnowledgeStore init failed: %s", exc)
            self._index = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        namespace: str = _DEFAULT_NAMESPACE,
        top_k: int = _TOP_K_DEFAULT,
        filter_metadata: dict | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform semantic search and return ranked results.

        Returns a list of dicts:
          {
            "id": str,
            "score": float,
            "text": str,          # the source text chunk
            "metadata": dict,     # arbitrary metadata stored at upsert time
          }
        """
        if self._index is None:
            logger.warning("KnowledgeStore.search called but index unavailable.")
            return []

        try:
            embedding = self._embedder.embed_query(query)
            query_params: dict[str, Any] = {
                "vector": embedding,
                "top_k": top_k,
                "namespace": namespace,
                "include_metadata": True,
            }
            if filter_metadata:
                query_params["filter"] = filter_metadata

            response = self._index.query(**query_params)
            results = []
            for match in response.get("matches", []):
                results.append({
                    "id": match["id"],
                    "score": match["score"],
                    "text": match.get("metadata", {}).get("text", ""),
                    "metadata": match.get("metadata", {}),
                })
            logger.debug(
                "KnowledgeStore: %d results for query '%s...' in ns=%s",
                len(results), query[:40], namespace,
            )
            return results
        except Exception as exc:
            logger.error("KnowledgeStore.search failed: %s", exc)
            return []

    def upsert(
        self,
        vectors: list[dict[str, Any]],
        namespace: str = _DEFAULT_NAMESPACE,
    ) -> int:
        """
        Upsert pre-computed vectors into Pinecone.

        Each item in `vectors` must have:
          {"id": str, "values": list[float], "metadata": dict}

        Returns the number of vectors upserted.
        """
        if self._index is None:
            return 0
        try:
            self._index.upsert(vectors=vectors, namespace=namespace)
            logger.info("Upserted %d vectors into ns=%s", len(vectors), namespace)
            return len(vectors)
        except Exception as exc:
            logger.error("KnowledgeStore.upsert failed: %s", exc)
            return 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch-embed a list of strings. Used by the seed script."""
        return self._embedder.embed_documents(texts)

    def health_check(self) -> bool:
        """Return True if the index is reachable."""
        try:
            if self._index:
                self._index.describe_index_stats()
                return True
        except Exception:
            pass
        return False
