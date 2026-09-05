import json
import math
import re
from typing import List, Dict, Any, Optional, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge import KnowledgeDoc
from app.core.logger import logger
from app.core.access import filter_items_by_access_tags


def _tokenize(text: str) -> List[str]:
    """Simple alphanumeric tokenizer."""
    return re.findall(r"\b\w+\b", text.lower())


def _bm25_score(query_tokens: List[str], doc_tokens: List[str], avg_doc_len: float) -> float:
    """Computes a lightweight BM25-like lexical relevance score."""
    if not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    k1 = 1.5
    b = 0.75
    score = 0.0
    doc_token_counts = {}
    for t in doc_tokens:
        doc_token_counts[t] = doc_token_counts.get(t, 0) + 1

    for q in query_tokens:
        if q in doc_token_counts:
            freq = doc_token_counts[q]
            tf = (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * (doc_len / (avg_doc_len or 1.0))))
            score += tf
    return score


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class RAGEngine:
    """Lightweight In-Process Hybrid Search & Knowledge Base Retrieval."""

    @staticmethod
    async def retrieve_relevant_context(
        db: AsyncSession,
        query: str,
        top_k: int = 3,
        query_embedding: Optional[List[float]] = None,
        allowed_access_tags: Optional[Set[str]] = None,
    ) -> str:
        """Retrieves top relevant knowledge base chunks for a user query."""
        if not query.strip():
            return ""

        stmt = select(KnowledgeDoc)
        result = await db.execute(stmt)
        docs = list(result.scalars().all())

        if allowed_access_tags is not None:
            docs = filter_items_by_access_tags(docs, allowed_access_tags, tag_attr="access_tags_json")

        if not docs:
            return ""

        query_tokens = _tokenize(query)
        if not query_tokens:
            return ""

        # Compute average doc token length
        doc_tokens_map = {doc.id: _tokenize(f"{doc.title} {doc.content} {doc.tags or ''}") for doc in docs}
        avg_len = sum(len(t) for t in doc_tokens_map.values()) / max(len(docs), 1)

        scored_docs = []
        for doc in docs:
            tokens = doc_tokens_map[doc.id]
            lexical_score = _bm25_score(query_tokens, tokens, avg_len)

            # Vector score if available
            vector_score = 0.0
            if query_embedding and doc.embedding_json:
                try:
                    doc_emb = json.loads(doc.embedding_json)
                    vector_score = _cosine_similarity(query_embedding, doc_emb)
                except Exception:
                    vector_score = 0.0

            # Combined hybrid score (lexical + vector)
            final_score = (lexical_score * 0.5) + (vector_score * 0.5)
            if final_score > 0.1 or lexical_score > 0.3:
                scored_docs.append((final_score, doc))

        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        top_docs = scored_docs[:top_k]

        if not top_docs:
            return ""

        context_snippets = []
        for score, doc in top_docs:
            context_snippets.append(f"### {doc.title} (Category: {doc.category or 'General'})\n{doc.content.strip()}")

        return "\n\n".join(context_snippets)
