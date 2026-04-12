"""
gemini_client.py — VitalMind Gemini AI Client

Central singleton wrapper providing:
  - get_llm()        → ChatGoogleGenerativeAI (Gemini 1.5 Flash)
  - get_embeddings() → GoogleGenerativeAIEmbeddings (text-embedding-004)
  - moderate_content() → Custom keyword safety filter (replaces OpenAI moderation)
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safety keyword filter — replaces OpenAI moderation API
# ---------------------------------------------------------------------------

_MODERATION_KEYWORDS = [
    # Self-harm / suicidality
    r"\b(kill\s+myself|suicide|self.harm|cutting\s+myself|end\s+my\s+life|want\s+to\s+die)\b",
    # Violence toward others
    r"\b(kill\s+(you|him|her|them)|murder|bomb|attack|shoot|stab)\b",
    # CSAM indicators
    r"\b(child\s+porn|cp\s+link|minors?\s+naked)\b",
    # Dangerous medical advice markers
    r"\b(overdose\s+on|inject\s+(bleach|poison)|drink\s+acid)\b",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _MODERATION_KEYWORDS]

EMERGENCY_PHRASES = [
    "chest pain", "can't breathe", "cannot breathe", "shortness of breath",
    "heart attack", "stroke", "seizure", "unconscious", "not breathing",
    "severe bleeding", "overdose", "allergic reaction", "anaphylaxis",
]


def moderate_content(text: str) -> dict:
    """
    Simple keyword-based content moderation replacing the OpenAI moderation API.

    Returns a dict matching a subset of the OpenAI moderation response shape:
      {
        "flagged": bool,
        "categories": { "self-harm": bool, "violence": bool, "hate": bool },
        "emergency_detected": bool,
        "matched_phrases": list[str],
      }
    """
    flagged = False
    matched: list[str] = []
    categories = {"self-harm": False, "violence": False, "hate": False}

    for i, pattern in enumerate(_COMPILED_PATTERNS):
        if pattern.search(text):
            flagged = True
            matched.append(_MODERATION_KEYWORDS[i])
            if i == 0:
                categories["self-harm"] = True
            elif i == 1:
                categories["violence"] = True

    text_lower = text.lower()
    emergency_detected = any(phrase in text_lower for phrase in EMERGENCY_PHRASES)

    return {
        "flagged": flagged,
        "categories": categories,
        "emergency_detected": emergency_detected,
        "matched_phrases": matched,
    }


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def get_llm(temperature: float = 0, streaming: bool = False, timeout: Optional[int] = None):
    """
    Return a configured ChatGoogleGenerativeAI instance (Gemini 1.5 Flash).
    Requires GOOGLE_API_KEY in the environment.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set; Gemini LLM calls will fail.")

    kwargs = dict(
        model="gemini-2.0-flash",
        temperature=temperature,
        google_api_key=api_key,
        streaming=streaming,
          # Gemini requires this for SystemMessage compat
    )
    if timeout:
        kwargs["request_timeout"] = timeout

    return ChatGoogleGenerativeAI(**kwargs)


# ---------------------------------------------------------------------------
# Embeddings factory
# ---------------------------------------------------------------------------

def get_embeddings():
    """
    Return a GoogleGenerativeAIEmbeddings instance using models/text-embedding-004.
    Dimension: 768.
    """
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set; embeddings will fail.")

    return GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=api_key,
    )
