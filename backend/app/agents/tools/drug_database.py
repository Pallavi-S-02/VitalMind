"""
drug_database.py — LangChain tools for drug interaction analysis.

Tools provided:
  - check_drug_interactions      : Pairwise interaction check via Pinecone + heuristics
  - validate_drug_dosage         : Validates dosage against patient profile constraints
  - cross_reference_drug_allergy : Checks drug against patient's known allergies
  - search_drug_knowledge_base   : RAG over drug knowledge embeddings in Pinecone
  - get_drug_schedule            : Generates an optimized dosing schedule
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Local knowledge: known high-risk interaction pairs
# Used as an instant safety net before LLM/Pinecone lookup
# ─────────────────────────────────────────────────────────────────────────────

_KNOWN_INTERACTIONS: dict[frozenset, dict] = {
    frozenset({"warfarin", "aspirin"}): {
        "severity": "MAJOR",
        "mechanism": "Both inhibit platelet function/coagulation, greatly increasing bleeding risk.",
        "clinical_effect": "Severe or fatal bleeding",
    },
    frozenset({"warfarin", "ibuprofen"}): {
        "severity": "MAJOR",
        "mechanism": "NSAIDs inhibit platelet aggregation and may displace warfarin from protein binding.",
        "clinical_effect": "Increased anticoagulant effect and GI bleeding risk",
    },
    frozenset({"warfarin", "naproxen"}): {
        "severity": "MAJOR",
        "mechanism": "NSAID potentiates anticoagulation and increases GI bleeding risk.",
        "clinical_effect": "Increased bleeding risk",
    },
    frozenset({"ssri", "maoi"}): {
        "severity": "CONTRAINDICATED",
        "mechanism": "Combined serotonin reuptake inhibition + MAO inhibition → serotonin syndrome.",
        "clinical_effect": "Serotonin syndrome: hyperthermia, seizures, death",
    },
    frozenset({"fluoxetine", "selegiline"}): {
        "severity": "CONTRAINDICATED",
        "mechanism": "SSRI + MAO-B inhibitor causes serotonin syndrome.",
        "clinical_effect": "Potentially fatal serotonin syndrome",
    },
    frozenset({"sertraline", "tramadol"}): {
        "severity": "MAJOR",
        "mechanism": "Serotonergic effects combined; tramadol lowers seizure threshold.",
        "clinical_effect": "Serotonin syndrome, increased seizure risk",
    },
    frozenset({"simvastatin", "amiodarone"}): {
        "severity": "MAJOR",
        "mechanism": "Amiodarone inhibits CYP3A4, dramatically raising simvastatin levels.",
        "clinical_effect": "Rhabdomyolysis, myopathy",
    },
    frozenset({"metformin", "contrast dye"}): {
        "severity": "MAJOR",
        "mechanism": "Iodinated contrast can cause acute kidney injury; metformin accumulates → lactic acidosis.",
        "clinical_effect": "Lactic acidosis",
    },
    frozenset({"digoxin", "amiodarone"}): {
        "severity": "MAJOR",
        "mechanism": "Amiodarone raises digoxin plasma levels by inhibiting elimination.",
        "clinical_effect": "Digoxin toxicity: arrhythmia, bradycardia",
    },
    frozenset({"methotrexate", "nsaid"}): {
        "severity": "MAJOR",
        "mechanism": "NSAIDs reduce renal clearance of methotrexate.",
        "clinical_effect": "Methotrexate toxicity: bone marrow suppression",
    },
    frozenset({"lisinopril", "potassium"}): {
        "severity": "MODERATE",
        "mechanism": "ACE inhibitors reduce aldosterone → elevated potassium.",
        "clinical_effect": "Hyperkalemia, cardiac arrhythmias",
    },
    frozenset({"ciprofloxacin", "antacid"}): {
        "severity": "MODERATE",
        "mechanism": "Divalent cations chelate fluoroquinolones, reducing absorption.",
        "clinical_effect": "Reduced ciprofloxacin efficacy",
    },
    frozenset({"sildenafil", "nitrate"}): {
        "severity": "CONTRAINDICATED",
        "mechanism": "Both drugs potentiate NO-mediated vasodilation synergistically.",
        "clinical_effect": "Severe hypotension, cardiac collapse",
    },
    frozenset({"clopidogrel", "omeprazole"}): {
        "severity": "MODERATE",
        "mechanism": "Omeprazole inhibits CYP2C19, reducing clopidogrel activation.",
        "clinical_effect": "Reduced antiplatelet efficacy",
    },
    frozenset({"lithium", "ibuprofen"}): {
        "severity": "MAJOR",
        "mechanism": "NSAIDs reduce renal lithium clearance.",
        "clinical_effect": "Lithium toxicity: tremor, altered consciousness",
    },
}

_ALLERGY_CROSS_REACTIONS: dict[str, list[str]] = {
    "penicillin": ["amoxicillin", "ampicillin", "piperacillin", "nafcillin", "cephalosporins"],
    "sulfa": ["sulfamethoxazole", "trimethoprim-sulfamethoxazole", "sulfasalazine", "thiazide diuretics"],
    "aspirin": ["ibuprofen", "naproxen", "diclofenac", "celecoxib", "indomethacin"],
    "codeine": ["morphine", "oxycodone", "hydrocodone", "tramadol", "fentanyl"],
    "latex": [],
    "contrast dye": ["iodine-containing compounds"],
}


def _normalize_drug_name(name: str) -> str:
    """Lowercase and strip whitespace for consistent comparison."""
    return name.lower().strip()


def _check_local_interactions(drug_a: str, drug_b: str) -> Optional[dict]:
    """Check the local high-risk interaction dictionary first (fast, no I/O)."""
    a = _normalize_drug_name(drug_a)
    b = _normalize_drug_name(drug_b)
    pair = frozenset({a, b})

    # Direct match
    if pair in _KNOWN_INTERACTIONS:
        return _KNOWN_INTERACTIONS[pair]

    # Partial/class-level match (e.g., "nsaid" class)
    for known_pair, info in _KNOWN_INTERACTIONS.items():
        for keyword in known_pair:
            if keyword in a or keyword in b:
                alt_pair = {k for k in known_pair if k != keyword}
                if alt_pair:
                    other = next(iter(alt_pair))
                    if other in a or other in b:
                        return info
    return None


# ─────────────────────────────────────────────────────────────────────────────
# LangChain tools
# ─────────────────────────────────────────────────────────────────────────────


@tool
def check_drug_interactions(drug_a: str, drug_b: str) -> str:
    """
    Check for a known interaction between two specific drugs.

    Searches a local high-risk interaction database and then falls back to
    a semantic knowledge base search for less common interactions.

    Args:
        drug_a: Name of the first medication
        drug_b: Name of the second medication

    Returns:
        A string describing the interaction severity, mechanism, and clinical
        effect, or a 'no significant interaction found' message.
    """
    local = _check_local_interactions(drug_a, drug_b)
    if local:
        return (
            f"⚠️ Interaction found: {drug_a} + {drug_b}\n"
            f"Severity: {local['severity']}\n"
            f"Mechanism: {local['mechanism']}\n"
            f"Clinical Effect: {local['clinical_effect']}"
        )

    # Fallback: Pinecone semantic search
    try:
        from app.agents.memory.knowledge_store import KnowledgeStore
        ks = KnowledgeStore()
        results = ks.search(
            query=f"drug interaction {drug_a} {drug_b}",
            namespace="drug_interactions",
            top_k=3,
        )
        if results and results.strip() and len(results) > 50:
            return f"Knowledge base results for {drug_a} + {drug_b}:\n{results}"
    except Exception as exc:
        logger.warning("Pinecone drug lookup failed: %s", exc)

    return (
        f"No significant documented interaction found between {drug_a} and {drug_b} "
        f"in the local database. Always verify with a clinical pharmacist or "
        f"prescribing database (e.g., Lexicomp, Micromedex)."
    )


@tool
def check_all_drug_interactions(medications: str) -> str:
    """
    Check all pairwise interactions for a comma-separated medication list.

    Performs an exhaustive pairwise check across all medications and returns
    a consolidated interaction report sorted by severity.

    Args:
        medications: Comma-separated list of medication names
                     e.g. "warfarin, aspirin, lisinopril, metformin"

    Returns:
        A formatted report of all interactions found, ranked by severity.
    """
    drug_list = [d.strip() for d in medications.split(",") if d.strip()]

    if len(drug_list) < 2:
        return "Please provide at least two medications to check interactions."

    findings = []
    checked = set()

    logger.info("LocalInteractionCheck: Checking medications: %s", drug_list)

    for i, drug_a in enumerate(drug_list):
        for drug_b in drug_list[i + 1 :]:
            norm_a = _normalize_drug_name(drug_a)
            norm_b = _normalize_drug_name(drug_b)
            pair_key = frozenset({norm_a, norm_b})
            
            if pair_key in checked:
                continue
            checked.add(pair_key)

            logger.info("LocalInteractionCheck: Testing pair {%s, %s}", norm_a, norm_b)
            local = _check_local_interactions(norm_a, norm_b)
            if local:
                logger.warning("LocalInteractionCheck: MATCH FOUND! %s + %s -> %s", norm_a, norm_b, local["severity"])
                findings.append({
                    "pair": f"{drug_a} + {drug_b}",
                    "severity": local["severity"],
                    "mechanism": local["mechanism"],
                    "clinical_effect": local["clinical_effect"],
                })

    if not findings:
        # Try Pinecone for any cross-combinations
        try:
            from app.agents.memory.knowledge_store import KnowledgeStore
            ks = KnowledgeStore()
            query = "drug interactions between: " + ", ".join(drug_list)
            kb_results = ks.search(query=query, namespace="drug_interactions", top_k=5)
            if kb_results and len(kb_results) > 50:
                return f"Knowledge base interaction results:\n{kb_results}"
        except Exception as exc:
            logger.warning("Pinecone pairwise lookup failed: %s", exc)

        return (
            f"✅ No high-risk interactions detected among: {', '.join(drug_list)}.\n"
            "This does not guarantee safety. Please verify with a clinical pharmacist."
        )

    # Sort by severity priority
    severity_order = {"CONTRAINDICATED": 0, "MAJOR": 1, "MODERATE": 2, "MINOR": 3}
    findings.sort(key=lambda x: severity_order.get(x["severity"], 4))

    lines = [f"⚠️ Drug Interaction Report ({len(findings)} interaction(s) found)\n"]
    lines.append("=" * 60)

    for f in findings:
        severity_emoji = {
            "CONTRAINDICATED": "🚫",
            "MAJOR": "🔴",
            "MODERATE": "🟡",
            "MINOR": "🟢",
        }.get(f["severity"], "⚠️")

        lines.append(
            f"\n{severity_emoji} {f['severity']}: {f['pair']}\n"
            f"  Mechanism: {f['mechanism']}\n"
            f"  Clinical Effect: {f['clinical_effect']}"
        )

    lines.append("\n" + "=" * 60)
    lines.append("⚕️ Consult your prescribing physician or pharmacist before making any changes.")

    return "\n".join(lines)


@tool
def validate_drug_dosage(
    drug_name: str,
    prescribed_dose: str,
    patient_age: str,
    patient_weight_kg: str,
    renal_function: str,
) -> str:
    """
    Validate a medication dosage against patient-specific parameters.

    Checks whether a prescribed dose is appropriate given the patient's age,
    weight, and renal/hepatic function using standard clinical guidelines.

    Args:
        drug_name: Name of the medication
        prescribed_dose: Prescribed dose as a string (e.g., "500mg twice daily")
        patient_age: Patient age in years as a string
        patient_weight_kg: Patient weight in kilograms as a string
        renal_function: eGFR value or description (e.g., "60 mL/min", "normal", "stage 3 CKD")

    Returns:
        A dosage validation assessment with recommendations if adjustments needed.
    """
    # Attempt Pinecone lookup for dosage guidelines
    try:
        from app.agents.memory.knowledge_store import KnowledgeStore
        ks = KnowledgeStore()
        query = (
            f"dosage guidelines for {drug_name} in patient age {patient_age} "
            f"weight {patient_weight_kg}kg renal function {renal_function}"
        )
        kb_result = ks.search(query=query, namespace="drug_dosages", top_k=3)
    except Exception as exc:
        logger.warning("Dosage KB lookup failed: %s", exc)
        kb_result = ""

    # Basic heuristic checks
    warnings = []
    try:
        age = int(patient_age)
        if age >= 65:
            warnings.append(
                f"⚠️ Geriatric patient (age {age}): Consider dose reduction per Beers Criteria. "
                "Many drugs have reduced clearance in elderly patients."
            )
        if age < 18:
            warnings.append(
                f"⚠️ Pediatric patient (age {age}): Weight-based dosing required. "
                f"Verify pediatric-specific dose for {drug_name}."
            )
    except ValueError:
        pass

    renal_lower = renal_function.lower()
    if any(term in renal_lower for term in ["ckd", "stage 3", "stage 4", "stage 5", "dialysis", "30", "15"]):
        warnings.append(
            f"⚠️ Impaired renal function: {renal_function}. "
            f"Review dosage adjustment requirements for {drug_name} — many drugs require "
            "dose reduction or extended intervals with reduced eGFR."
        )

    result_lines = [
        f"📋 Dosage Assessment: {drug_name} — {prescribed_dose}",
        f"   Patient: Age {patient_age}, Weight {patient_weight_kg}kg, Renal: {renal_function}",
        "",
    ]

    if warnings:
        result_lines.append("⚠️ Clinical Considerations:")
        result_lines.extend(f"  {w}" for w in warnings)
    else:
        result_lines.append("✅ No major dosage flags based on patient parameters.")

    if kb_result and len(kb_result) > 30:
        result_lines += ["", "📚 Clinical Guideline Reference:", kb_result[:600]]

    result_lines.append("\n⚕️ Final dosage must be confirmed by the prescribing clinician.")

    return "\n".join(result_lines)


@tool
def cross_reference_drug_allergy(drug_name: str, patient_allergies: str) -> str:
    """
    Cross-reference a medication against the patient's known allergy profile.

    Checks for direct allergy matches and cross-reactivity with related
    drug classes (e.g., penicillin allergy → amoxicillin cross-reactivity).

    Args:
        drug_name: Name of the medication to check
        patient_allergies: Comma-separated list of known patient allergies

    Returns:
        A safety assessment identifying direct and cross-reactive allergy risks.
    """
    allergies = [a.strip().lower() for a in patient_allergies.split(",") if a.strip()]
    drug = _normalize_drug_name(drug_name)

    direct_match = None
    cross_reactions = []

    for allergy in allergies:
        # Direct match
        if allergy in drug or drug in allergy:
            direct_match = allergy

        # Cross-reactivity check
        cross_react_drugs = _ALLERGY_CROSS_REACTIONS.get(allergy, [])
        for cross_drug in cross_react_drugs:
            if cross_drug in drug or drug in cross_drug:
                cross_reactions.append((allergy, cross_drug))

    if direct_match:
        return (
            f"🚫 ALLERGY ALERT: {drug_name} matches a known patient allergy to '{direct_match}'.\n"
            f"DO NOT administer. Document allergy and substitute with an alternative."
        )

    if cross_reactions:
        lines = [f"⚠️ Cross-Reactivity Warning for {drug_name}:"]
        for allergy, cross_drug in cross_reactions:
            lines.append(
                f"  Patient is allergic to '{allergy}' which may cross-react with '{drug_name}'.\n"
                f"  Cross-reactive agent: {cross_drug}"
            )
        lines.append("\nProceed with caution. Consider skin testing or alternative medication.")
        return "\n".join(lines)

    if not allergies:
        return f"ℹ️ No allergies documented for this patient. Cannot perform allergy check for {drug_name}."

    return (
        f"✅ No allergy conflicts detected for {drug_name}.\n"
        f"Checked against: {', '.join(allergies)}"
    )


@tool
def search_drug_knowledge_base(query: str) -> str:
    """
    Perform a semantic search over the drug interaction and pharmacology knowledge base.

    Use this for nuanced questions about drug mechanisms, rare interactions,
    drug-food interactions, or clinical pharmacology guidelines that
    aren't covered by the local interaction dictionary.

    Args:
        query: Natural language query about drug pharmacology or interactions
               e.g. "Can I take metformin with alcohol?" or
               "warfarin and grapefruit juice interaction"

    Returns:
        Relevant clinical excerpts from the drug knowledge base.
    """
    try:
        from app.agents.memory.knowledge_store import KnowledgeStore
        ks = KnowledgeStore()
        results = ks.search(query=query, namespace="drug_interactions", top_k=5)
        if results and len(results) > 30:
            return f"Drug Knowledge Base Results:\n{results}"
        return "No relevant entries found in the drug knowledge base for this query."
    except Exception as exc:
        logger.error("Drug KB search failed: %s", exc)
        return f"Knowledge base search unavailable: {exc}"


@tool
def generate_medication_schedule(medications: str, patient_lifestyle: str) -> str:
    """
    Generate an optimized medication dosing schedule for a patient.

    Considers medication timing requirements (with/without food, specific times),
    interaction timing (drugs that shouldn't be taken together), and patient
    lifestyle factors to create a practical daily schedule.

    Args:
        medications: Comma-separated medication list with doses
                     e.g. "metformin 500mg twice daily, lisinopril 10mg once daily"
        patient_lifestyle: Brief description of patient routine
                           e.g. "works night shift, diabetic, takes meals at 7am/1pm/7pm"

    Returns:
        A formatted daily medication schedule with timing rationale.
    """
    if not medications.strip():
        return "No medications provided to schedule."

    drug_list = [m.strip() for m in medications.split(",") if m.strip()]

    # Basic timing heuristics
    timing_rules: dict[str, str] = {
        "metformin": "with meals (reduces GI side effects)",
        "levothyroxine": "30-60 minutes before breakfast on empty stomach",
        "bisphosphonate": "first thing in morning, 30 mins before food, remain upright",
        "warfarin": "same time every evening for consistent INR levels",
        "lisinopril": "any time of day, avoid potassium supplements",
        "simvastatin": "evening (cholesterol synthesis peaks at night)",
        "atorvastatin": "any time — not time-sensitive",
        "aspirin": "morning with food",
        "ssri": "morning (may cause insomnia if taken at night)",
        "prednisone": "morning with food (mimics natural cortisol rhythm)",
        "proton pump inhibitor": "30-60 minutes before largest meal",
        "antibiotic": "evenly spaced intervals (e.g., every 8h or 12h)",
    }

    schedule_lines = [
        f"📅 Personalized Medication Schedule",
        f"Patient routine: {patient_lifestyle}",
        "=" * 50,
        "",
    ]

    found_rules = []
    unscheduled = []

    for drug in drug_list:
        drug_lower = drug.lower()
        matched = False
        for keyword, timing in timing_rules.items():
            if keyword in drug_lower:
                found_rules.append(f"  • {drug}: Take {timing}")
                matched = True
                break
        if not matched:
            unscheduled.append(drug)

    if found_rules:
        schedule_lines.append("🕐 Timing Recommendations:")
        schedule_lines.extend(found_rules)

    if unscheduled:
        schedule_lines.append("\n📌 Standard Timing (consult pharmacist for specific timing):")
        for drug in unscheduled:
            schedule_lines.append(f"  • {drug}: Follow prescriber instructions")

    schedule_lines += [
        "",
        "💡 General Tips:",
        "  • Use a pill organizer to track daily doses",
        "  • Set phone alarms for each medication time",
        "  • Never double-dose if you miss one — follow package insert",
        "  • Keep a medication diary for your next appointment",
        "",
        "⚕️ Schedule generated as a guide only. Confirm timing with your pharmacist.",
    ]

    return "\n".join(schedule_lines)
