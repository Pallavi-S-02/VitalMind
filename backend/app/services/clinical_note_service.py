import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.models.db import db
from app.models.report import MedicalReport

logger = logging.getLogger(__name__)

CLINICAL_NOTE_PROMPT = """You are an expert medical scribe. Convert this raw consultation transcript
into a formal, highly structured SOAP clinical note.

Patient history & context goes into SUBJECTIVE.
Observations, vital signs, physical exam elements go into OBJECTIVE.
Diagnoses and clinical impressions go into ASSESSMENT.
Medications, tests, and follow-ups go into PLAN.

If a section has no details, leave it as an empty object or null, but try to infer from the text.
The 'summary' should be a concise 1-2 sentence overview of the entire visit.

Transcript:
{transcript}

Ensure high clinical accuracy. Respond with ONLY valid JSON:
{{
  "summary": "<1-2 sentence visit summary>",
  "soap": {{
    "subjective": {{
      "chief_complaint": "",
      "history_of_present_illness": "",
      "review_of_systems": [],
      "current_medications": [],
      "allergies": []
    }},
    "objective": {{
      "vitals": {{}},
      "physical_exam": []
    }},
    "assessment": {{
      "diagnoses": [],
      "differential_diagnoses": []
    }},
    "plan": {{
      "medications": [],
      "diagnostics": [],
      "therapeutic": [],
      "patient_education": [],
      "follow_up": ""
    }}
  }}
}}
"""

class ClinicalNoteService:
    @staticmethod
    def generate_note_from_voice_session(
        session_id: str, 
        patient_id: str, 
        history: list[dict], 
        doctor_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Converts a voice session history into a structured SOAP clinical note,
        and saves it to the MedicalReport table.
        Returns the generated MedicalReport ID.
        """
        if not history:
            logger.warning("ClinicalNoteService: No history provided for session %s", session_id)
            return None

        # Format transcript
        formatted_transcript = []
        for turn in history:
            role = turn.get("role", "unknown").upper()
            text = turn.get("transcript", "").strip()
            if text:
                formatted_transcript.append(f"{role}: {text}")
        
        full_transcript = "\n".join(formatted_transcript)

        try:
            # 1. Generate JSON using LLM
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash", temperature=0,
                google_api_key=__import__("os").getenv("GOOGLE_API_KEY"),
                
                request_timeout=15,
            )
            prompt = CLINICAL_NOTE_PROMPT.format(transcript=full_transcript)
            
            response = llm.invoke([SystemMessage(content=prompt)])
            
            result = json.loads(response.content)
            summary = result.get("summary", "Clinical Note Generated from Voice Session")
            soap_data = result.get("soap", {})

            # 2. Add metadata
            structured_data = {
                "source": "voice_ambient_session",
                "session_id": session_id,
                "soap": soap_data,
                "raw_transcript_length": len(full_transcript)
            }

            # 3. Save as MedicalReport
            report_id = str(uuid.uuid4())
            new_report = MedicalReport(
                id=report_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                title=f"Clinical Consultation Note - {datetime.now(timezone.utc).strftime('%b %d, %Y')}",
                type="clinical_note",
                date=datetime.now(timezone.utc).date(),
                summary=summary,
                structured_data=structured_data
            )

            db.session.add(new_report)
            db.session.commit()
            
            logger.info("ClinicalNoteService: Generated note %s for session %s", report_id, session_id)
            return report_id

        except Exception as exc:
            logger.error("ClinicalNoteService: Failed to generate note for session %s: %s", session_id, exc)
            db.session.rollback()
            return None

    @staticmethod
    def create_manual_note(patient_id, doctor_id, title, soap_data):
        """
        Creates a manual clinical note from structured SOAP data.
        """
        try:
            report_id = str(uuid.uuid4())
            
            # Simple summary from assessment or default
            summary = soap_data.get('assessment', 'Manual clinical consultation record.')
            if isinstance(summary, str) and len(summary) > 200:
                summary = summary[:197] + "..."

            structured_data = {
                "source": "manual_entry",
                "soap": soap_data
            }

            new_report = MedicalReport(
                id=report_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                title=title or f"Clinical Note - {datetime.now(timezone.utc).strftime('%b %d, %Y')}",
                type="clinical_note",
                date=datetime.now(timezone.utc).date(),
                summary=summary,
                structured_data=structured_data
            )

            db.session.add(new_report)
            db.session.commit()
            
            logger.info("ClinicalNoteService: Created manual note %s for patient %s", report_id, patient_id)
            return new_report
        except Exception as exc:
            logger.error("ClinicalNoteService: Failed to create manual note: %s", exc)
            db.session.rollback()
            return None
