"""
urgency_scoring.py — Rule-based urgency scoring tool for the Symptom Analyst.

Implements a weighted symptom scoring system to detect when a patient
needs immediate emergency care versus urgent or routine attention.
The scoring is deterministic and does NOT require an LLM call, making
it fast and reliable as a safety guardrail.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

UrgencyLevel = Literal["emergency", "urgent", "routine"]

# ---------------------------------------------------------------------------
# Keyword rule engine
# ---------------------------------------------------------------------------

# Score ≥ 8  → emergency
# Score 4-7  → urgent
# Score 0-3  → routine
MAX_EMERGENCY_SCORE = 8
MAX_URGENT_SCORE = 4

# (pattern, score, label)
EMERGENCY_PATTERNS: list[tuple[str, int, str]] = [
    # Cardiac
    (r"\bchest pain\b", 3, "chest pain"),
    (r"\bheart attack\b", 5, "stated heart attack"),
    (r"\bchest pressure\b", 3, "chest pressure"),
    (r"\bleft arm\b.*\bpain\b", 3, "left arm pain"),
    (r"\bjaw pain\b", 2, "jaw pain"),
    # Respiratory
    (r"\bcan't breathe\b|\bcannot breathe\b|\bcan not breathe\b", 5, "severe breathing difficulty"),
    (r"\bshortness of breath\b|\bsob\b", 2, "shortness of breath"),
    (r"\bchoking\b", 4, "choking"),
    # Neurological / Stroke
    (r"\bstroke\b", 5, "stated stroke"),
    (r"\bface drooping\b|\bfacial droop\b", 3, "facial drooping"),
    (r"\barm weakness\b|\bone arm\b", 2, "arm weakness"),
    (r"\bslurred speech\b|\bspeech difficulty\b", 2, "speech difficulty"),
    (r"\bsudden severe headache\b|\bworst headache\b", 4, "thunderclap headache"),
    (r"\bunconscious\b|\bpassed out\b|\bloss of consciousness\b", 5, "loss of consciousness"),
    # Bleeding
    (r"\bsevere bleeding\b|\bharemorrhage\b|\bheavy bleeding\b", 4, "severe bleeding"),
    (r"\bcoughing blood\b|\bcoughing up blood\b", 3, "hemoptysis"),
    # Anaphylaxis
    (r"\bthroat\b.*\bswelling\b|\bswelling\b.*\bthroat\b", 4, "throat swelling"),
    (r"\banaphylaxis\b|\bsevere allergic reaction\b", 5, "anaphylaxis"),
    # Suicide / Self-harm
    (r"\bsuicid\b|\bwant to die\b|\bkill myself\b|\bself.harm\b", 5, "mental health emergency"),
    # Overdose
    (r"\boverdose\b|\btook too many\b", 4, "potential overdose"),
    # Pediatric
    (r"\bnot breathing\b|\bstop breathing\b", 5, "apnea"),
    # Severity modifiers
    (r"\bsevere\b", 1, "severe modifier"),
    (r"\bexcruciating\b|\bworst ever\b|\b10.*10\b", 2, "extreme pain descriptor"),
]


@dataclass
class UrgencyResult:
    level: UrgencyLevel
    score: int
    triggers: list[str] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self):
        return {
            "urgency_level": self.level,
            "urgency_score": self.score,
            "triggers": self.triggers,
            "recommendation": self.recommendation,
        }


def score_symptoms(symptom_text: str) -> UrgencyResult:
    """
    Run the rule engine against a symptom description.
    Returns an UrgencyResult with the scoring details.
    """
    text = symptom_text.lower()
    total_score = 0
    triggers = []

    for pattern, weight, label in EMERGENCY_PATTERNS:
        if re.search(pattern, text):
            total_score += weight
            triggers.append(f"{label} (+{weight})")

    if total_score >= MAX_EMERGENCY_SCORE:
        level: UrgencyLevel = "emergency"
        recommendation = (
            "⚠️ EMERGENCY: Call 911 immediately or go to the nearest emergency room. "
            "Do not drive yourself. Stay calm and provide first aid if safe to do so."
        )
    elif total_score >= MAX_URGENT_SCORE:
        level = "urgent"
        recommendation = (
            "Please seek medical attention within the next few hours. "
            "Visit an urgent care center or call your doctor immediately. "
            "If symptoms worsen rapidly, call 911."
        )
    else:
        level = "routine"
        recommendation = (
            "Your symptoms appear non-emergency. Monitor them closely. "
            "Schedule an appointment with your GP if they persist or worsen."
        )

    logger.info(
        "Urgency scored: level=%s score=%d triggers=%s",
        level, total_score, triggers,
    )
    return UrgencyResult(
        level=level,
        score=total_score,
        triggers=triggers,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# LangChain tool
# ---------------------------------------------------------------------------

@tool
def calculate_urgency_score(symptom_description: str) -> str:
    """
    Calculate the medical urgency level for a patient's described symptoms.

    Uses a rule-based keyword scoring engine to detect emergency and urgent
    situations reliably without requiring an LLM call.

    ALWAYS call this tool early in symptom analysis to check for emergencies
    that require immediate action before proceeding with the interview.

    Args:
        symptom_description: The patient's description of their symptoms in plain text

    Returns:
        A formatted string with urgency level (emergency/urgent/routine), score,
        detected triggers, and recommended action.
    """
    result = score_symptoms(symptom_description)
    output_lines = [
        f"URGENCY ASSESSMENT",
        f"==================",
        f"Level: {result.level.upper()}",
        f"Score: {result.score}/10+",
        f"",
        f"Detected triggers:",
    ]
    if result.triggers:
        for t in result.triggers:
            output_lines.append(f"  • {t}")
    else:
        output_lines.append("  • No high-urgency keywords detected")

    output_lines += [
        f"",
        f"Recommendation: {result.recommendation}",
    ]
    return "\n".join(output_lines)
