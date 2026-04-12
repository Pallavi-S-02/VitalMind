"""
medical_kb.py — LangChain tool for semantic search over the Pinecone medical knowledge base.

Used by the Symptom Analyst, Drug Interaction, and Report Reader agents to RAG
relevant clinical context into the reasoning chain.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def search_medical_knowledge_base(query: str, namespace: str = "symptoms", top_k: int = 5) -> str:
    """
    Search the VitalMind medical knowledge base for clinically relevant information.

    Use this tool whenever you need to look up:
    - Symptom differentials and clinical presentations
    - Drug interactions and pharmacology
    - Lab value interpretation and reference ranges
    - Clinical guidelines and treatment protocols
    - Disease/condition information

    Args:
        query: A clinical question or symptom description to search for
        namespace: Knowledge domain to search. One of: "symptoms", "drugs", "labs", "conditions"
        top_k: Number of results to return (1-10, default 5)

    Returns:
        A formatted string of relevant clinical knowledge snippets
    """
    try:
        from app.agents.memory.knowledge_store import KnowledgeStore
        store = KnowledgeStore()
        results = store.search(query=query, namespace=namespace, top_k=min(top_k, 10))

        if not results:
            return f"No relevant information found in the '{namespace}' knowledge base for: {query}"

        formatted = []
        for i, r in enumerate(results, 1):
            score_pct = int(r["score"] * 100)
            formatted.append(
                f"[{i}] (Relevance: {score_pct}%)\n{r['text']}\n"
                f"Source: {r['metadata'].get('source', 'VitalMind KB')}"
            )

        return "\n\n---\n\n".join(formatted)

    except Exception as exc:
        logger.error("search_medical_knowledge_base failed: %s", exc)
        return f"Knowledge base search temporarily unavailable. Error: {exc}"


@tool
def search_drug_interactions(drug_names: str) -> str:
    """
    Search for known interactions between the listed medications.

    Args:
        drug_names: Comma-separated list of drug names (e.g., "warfarin, aspirin, metoprolol")

    Returns:
        Formatted interaction analysis from the medical knowledge base
    """
    try:
        from app.agents.memory.knowledge_store import KnowledgeStore
        store = KnowledgeStore()

        drugs = [d.strip() for d in drug_names.split(",")]
        query = f"drug interactions between: {', '.join(drugs)}"
        results = store.search(query=query, namespace="drugs", top_k=5)

        if not results:
            return f"No specific interaction data found for: {drug_names}"

        formatted = [f"Drug Interaction Analysis for: {drug_names}\n"]
        for i, r in enumerate(results, 1):
            formatted.append(f"[{i}] {r['text']}")

        return "\n\n".join(formatted)

    except Exception as exc:
        logger.error("search_drug_interactions failed: %s", exc)
        return f"Drug interaction search temporarily unavailable. Error: {exc}"
