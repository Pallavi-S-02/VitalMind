#!/usr/bin/env python3
"""
seed_knowledge_base.py — Bootstrap the Pinecone medical knowledge store.

Chunks a starter medical corpus, generates embeddings via OpenAI
text-embedding-3-large, and upserts into the vitalmind-kb Pinecone index.

Usage
-----
    cd backend
    source venv/bin/activate
    python scripts/seed_knowledge_base.py

Environment variables required:
    OPENAI_API_KEY
    PINECONE_API_KEY
    PINECONE_INDEX_NAME  (default: vitalmind-kb)
    PINECONE_CLOUD       (default: aws)
    PINECONE_REGION      (default: us-east-1)
"""

import os
import sys
import uuid
import logging
from pathlib import Path

# Allow running from backend/ or backend/scripts/
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Starter knowledge corpus (namespace → chunks)
# ---------------------------------------------------------------------------

KNOWLEDGE_CORPUS: dict[str, list[dict]] = {
    "symptoms": [
        {
            "text": (
                "Chest pain can be a symptom of many conditions. Cardiac chest pain "
                "(angina or myocardial infarction) typically presents as pressure, squeezing, "
                "or tightness in the center or left of the chest, often radiating to the left arm, "
                "jaw, or back. It may be accompanied by shortness of breath, sweating, nausea, or "
                "lightheadedness. Immediate emergency evaluation is required."
            ),
            "metadata": {"category": "cardiac", "urgency": "high", "source": "AHA Guidelines 2024"},
        },
        {
            "text": (
                "Shortness of breath (dyspnea) can result from pulmonary embolism, asthma, COPD, "
                "pneumonia, heart failure, or anxiety. Acute onset with pleuritic chest pain and "
                "risk factors (immobility, recent surgery, long travel) suggests pulmonary embolism. "
                "Wheezing with exertion or allergen exposure suggests asthma."
            ),
            "metadata": {"category": "respiratory", "urgency": "high", "source": "NICE Guidelines"},
        },
        {
            "text": (
                "Headache differential diagnosis: Tension headache (bilateral, band-like, mild-moderate) "
                "is the most common. Migraine (unilateral, pulsating, moderate-severe, with nausea/photophobia). "
                "Cluster headache (severe periorbital, unilateral, with autonomic features). "
                "Subarachnoid hemorrhage presents as thunderclap headache — worst headache of life — requiring "
                "immediate CT scan and LP if negative."
            ),
            "metadata": {"category": "neurology", "urgency": "variable", "source": "IHS Classification"},
        },
        {
            "text": (
                "Abdominal pain location guides diagnosis: RUQ pain suggests cholecystitis, hepatitis, or "
                "peptic ulcer. RLQ pain, especially with rebound tenderness and Rovsing sign, suggests "
                "appendicitis. LLQ pain with fever and change in bowel habits suggests diverticulitis. "
                "Epigastric pain relieved by food suggests duodenal ulcer; worsened by food suggests gastric ulcer."
            ),
            "metadata": {"category": "gastroenterology", "urgency": "variable", "source": "Schwartz Principles"},
        },
        {
            "text": (
                "Stroke FAST criteria: Face drooping (one side of face numb or droopy), Arm weakness "
                "(one arm weak or numb), Speech difficulty (slurred or unable to speak), Time to call 911. "
                "Additional symptoms: sudden vision loss in one or both eyes, sudden severe headache without cause, "
                "sudden trouble walking/loss of balance. Thrombolysis (tPA) window is 4.5 hours from onset — "
                "time is brain."
            ),
            "metadata": {"category": "neurology", "urgency": "emergency", "source": "ASA Stroke Guidelines"},
        },
        {
            "text": (
                "Fever classification: Low-grade 37.3-38°C, Moderate 38-39°C, High 39-40°C, Hyperpyrexia >40°C. "
                "Fever with rash and stiff neck suggests meningitis (emergency). Fever with localizing symptoms "
                "guides workup: cough → pneumonia, dysuria → UTI, RUQ pain + jaundice → cholangitis. "
                "Fever of unknown origin: >3 weeks temperature >38.3°C without diagnosis after 1 week investigation."
            ),
            "metadata": {"category": "infectious_disease", "urgency": "variable", "source": "Harrison's"},
        },
    ],
    "drugs": [
        {
            "text": (
                "Warfarin drug interactions: Warfarin is metabolized by CYP2C9 and has numerous interactions. "
                "Antibiotics (metronidazole, fluconazole, ciprofloxacin) inhibit warfarin metabolism, increasing "
                "bleeding risk — INR monitoring required. NSAIDs increase bleeding risk by inhibiting platelet "
                "function. Vitamin K-rich foods (leafy greens) reduce warfarin effect. St John's Wort induces "
                "CYP enzymes, reducing warfarin levels."
            ),
            "metadata": {"category": "anticoagulant", "drug": "warfarin", "source": "BNF 2024"},
        },
        {
            "text": (
                "Metformin is the first-line medication for type 2 diabetes. Mechanism: reduces hepatic glucose "
                "production, increases insulin sensitivity. Contraindicated with eGFR <30 mL/min due to lactic "
                "acidosis risk. Hold for 48h around iodinated contrast media. Common side effects: GI upset "
                "(nausea, diarrhea) — mitigated by taking with food and slow titration. No hypoglycemia when "
                "used as monotherapy."
            ),
            "metadata": {"category": "antidiabetic", "drug": "metformin", "source": "ADA Standards 2024"},
        },
        {
            "text": (
                "Statin drug interactions and safety: Statins are metabolized by CYP3A4 (atorvastatin, simvastatin) "
                "or CYP2C9 (rosuvastatin, fluvastatin). CYP3A4 inhibitors (clarithromycin, diltiazem, grapefruit) "
                "increase statin levels → myopathy risk. Fibrates combined with statins increase rhabdomyolysis risk. "
                "Monitor CK if myalgia develops. Statins are contraindicated in pregnancy (Category X)."
            ),
            "metadata": {"category": "cardiovascular", "drug": "statins", "source": "ACC/AHA 2023"},
        },
        {
            "text": (
                "ACE inhibitor considerations: Contraindicated in pregnancy (teratogenic — renal agenesis). "
                "Do not combine with ARBs or aliskiren due to dual RAAS blockade increasing AKI and hyperkalemia risk. "
                "NSAIDs reduce antihypertensive effect and increase AKI risk with ACE inhibitors. "
                "Hyperkalemia risk increased with potassium-sparing diuretics and potassium supplements. "
                "Monitor renal function and potassium within 1-2 weeks of starting or dose increase."
            ),
            "metadata": {"category": "cardiovascular", "drug": "ACE_inhibitors", "source": "JNC 8"},
        },
    ],
    "labs": [
        {
            "text": (
                "Complete Blood Count (CBC) interpretation: WBC 4.5-11.0 x10³/µL — elevated suggests infection/inflammation, "
                "low suggests immunosuppression or bone marrow suppression. Hemoglobin: men 13.5-17.5 g/dL, women 12-15.5 g/dL. "
                "MCV: microcytic <80 fL (iron deficiency, thalassemia), normocytic 80-100 fL, macrocytic >100 fL "
                "(B12/folate deficiency, hypothyroidism). Platelets 150-400 x10³/µL."
            ),
            "metadata": {"category": "hematology", "test": "CBC", "source": "Fischbach Lab Values"},
        },
        {
            "text": (
                "Lipid panel interpretation: Total cholesterol <200 mg/dL desirable. LDL goals vary by risk: "
                "high risk (prior CVD, diabetes) <70 mg/dL; moderate risk <100 mg/dL; low risk <130 mg/dL. "
                "HDL >60 mg/dL is protective; <40 mg/dL in men or <50 mg/dL in women is a risk factor. "
                "Triglycerides <150 mg/dL normal; 150-199 borderline; 200-499 high; ≥500 hypertriglyceridemia."
            ),
            "metadata": {"category": "cardiology", "test": "lipid_panel", "source": "ACC/AHA Cholesterol Guidelines"},
        },
        {
            "text": (
                "HbA1c interpretation for diabetes management: Normal <5.7%. Prediabetes 5.7-6.4%. "
                "Diabetes ≥6.5% (confirmed by repeat testing). Treatment targets: most adults <7.0%; "
                "older adults or complex patients <7.5-8.0%. HbA1c reflects average glucose over 2-3 months "
                "and is affected by conditions altering RBC lifespan (hemolytic anemia → falsely low; "
                "iron deficiency → falsely high)."
            ),
            "metadata": {"category": "endocrinology", "test": "HbA1c", "source": "ADA Standards 2024"},
        },
        {
            "text": (
                "Kidney function tests: Serum creatinine normal: men 0.74-1.35 mg/dL, women 0.59-1.04 mg/dL. "
                "eGFR stages: G1 ≥90, G2 60-89, G3a 45-59, G3b 30-44, G4 15-29, G5 <15 (kidney failure). "
                "BUN 7-20 mg/dL; BUN:creatinine ratio >20:1 suggests prerenal azotemia. "
                "Urine albumin-creatinine ratio >30 mg/g indicates albuminuria, a marker of CKD progression."
            ),
            "metadata": {"category": "nephrology", "test": "kidney_function", "source": "KDIGO 2024"},
        },
    ],
    "conditions": [
        {
            "text": (
                "Hypertension management: Stage 1: 130-139/80-89 mmHg. Stage 2: ≥140/90 mmHg. "
                "Lifestyle interventions: DASH diet, reduce sodium <2.3g/day, 150 min moderate exercise/week, "
                "weight loss, limit alcohol. First-line medications: thiazide diuretics, ACE inhibitors/ARBs, "
                "or CCBs. Black patients: prefer thiazides or CCBs. Diabetics: prefer ACE/ARB (renoprotective). "
                "Goal BP: <130/80 for most adults."
            ),
            "metadata": {"category": "cardiovascular", "condition": "hypertension", "source": "JNC 8 / ACC/AHA 2017"},
        },
        {
            "text": (
                "Type 2 Diabetes mellitus: Characterized by insulin resistance and relative insulin deficiency. "
                "Diagnostic criteria: fasting glucose ≥126 mg/dL, 2h OGTT ≥200 mg/dL, random glucose ≥200 with "
                "symptoms, or HbA1c ≥6.5%. Complications: microvascular (retinopathy, nephropathy, neuropathy) "
                "and macrovascular (CAD, stroke, PAD). Annual screening: ophthalmology, podiatry, urine albumin, "
                "eGFR, lipids, blood pressure."
            ),
            "metadata": {"category": "endocrinology", "condition": "type2_diabetes", "source": "ADA 2024"},
        },
        {
            "text": (
                "Asthma management (GINA 2024): Stepwise therapy. Step 1-2: as-needed SABA or low-dose ICS-formoterol. "
                "Step 3: Low-dose ICS-LABA. Step 4: Medium-dose ICS-LABA. Step 5: High-dose ICS-LABA + add-on therapy "
                "(tiotropium, biologics for severe eosinophilic asthma). Trigger avoidance: allergens, smoke, NSAIDs, "
                "beta-blockers. Spirometry: FEV1/FVC <0.7 with reversibility ≥12% and 200 mL post-bronchodilator."
            ),
            "metadata": {"category": "pulmonology", "condition": "asthma", "source": "GINA 2024"},
        },
    ],
}


# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------

BATCH_SIZE = 50  # Pinecone upsert batch size


def chunk_text(text: str, max_len: int = 500) -> list[str]:
    """Split long text into overlapping chunks."""
    words = text.split()
    chunks, current = [], []
    for word in words:
        current.append(word)
        if len(" ".join(current)) >= max_len:
            chunks.append(" ".join(current))
            current = current[-20:]  # 20-word overlap
    if current:
        chunks.append(" ".join(current))
    return chunks


def seed_namespace(namespace: str, items: list[dict], store) -> int:
    """Embed and upsert one namespace of documents. Returns count."""
    from app.agents.memory.knowledge_store import KnowledgeStore

    texts = []
    metadata_list = []

    for item in items:
        chunks = chunk_text(item["text"])
        for chunk in chunks:
            texts.append(chunk)
            metadata_list.append({**item.get("metadata", {}), "text": chunk})

    logger.info("Embedding %d chunks for namespace '%s'...", len(texts), namespace)
    embeddings = store.embed_texts(texts)

    vectors = [
        {
            "id": str(uuid.uuid4()),
            "values": emb,
            "metadata": meta,
        }
        for emb, meta in zip(embeddings, metadata_list)
    ]

    # Upsert in batches
    total = 0
    for i in range(0, len(vectors), BATCH_SIZE):
        batch = vectors[i : i + BATCH_SIZE]
        total += store.upsert(batch, namespace=namespace)

    return total


def main():
    logger.info("=" * 60)
    logger.info("VitalMind Knowledge Base Seeder")
    logger.info("=" * 60)

    # Validate env
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY is not set. Aborting.")
        sys.exit(1)
    if not os.getenv("PINECONE_API_KEY"):
        logger.error("PINECONE_API_KEY is not set. Aborting.")
        sys.exit(1)

    from app.agents.memory.knowledge_store import KnowledgeStore
    store = KnowledgeStore()

    if not store.health_check():
        logger.error("Pinecone index is not reachable. Aborting.")
        sys.exit(1)

    total_upserted = 0
    for namespace, items in KNOWLEDGE_CORPUS.items():
        count = seed_namespace(namespace, items, store)
        total_upserted += count
        logger.info("✓  Namespace '%s': %d vectors upserted.", namespace, count)

    logger.info("")
    logger.info("=" * 60)
    logger.info("Seeding complete. Total vectors: %d", total_upserted)
    logger.info("=" * 60)


if __name__ == "__main__":
    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except ImportError:
        pass
    main()
