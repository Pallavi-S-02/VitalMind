import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.agents.prompts.drug_prompts import MEDICATION_SCHEDULE_PROMPT

logger = logging.getLogger(__name__)

class AISchedulerService:
    @staticmethod
    def generate_optimized_schedule(medications_list, patient_profile=None):
        """
        Uses Gemini 2.5 Flash to generate a clinically-optimized medication schedule.
        
        Args:
            medications_list (list): List of medication/prescription dicts with dosage/frequency.
            patient_profile (dict): Optional patient context (lifestyle, allergies, conditions).
            
        Returns:
            str: Markdown-formatted medication schedule.
        """
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key:
            logger.error("GOOGLE_API_KEY not found in environment")
            return "Schedule generation unavailable (API key missing)."

        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-3-flash-preview",
                temperature=0.2,
                google_api_key=google_key
            )

            # Format medications for the prompt
            meds_str = ""
            for m in medications_list:
                name = m.get('medication_name') or m.get('name') or "Unknown Medication"
                dosage = m.get('dosage') or ""
                freq = m.get('frequency') or ""
                instr = m.get('instructions') or ""
                meds_str += f"- {name}: {dosage} {freq} ({instr})\n"

            # Format lifestyle context
            lifestyle = "Standard daily routine"
            if patient_profile:
                lifestyle = f"Age: {patient_profile.get('age', 'N/A')}, "
                lifestyle += f"Conditions: {', '.join(patient_profile.get('chronic_conditions', [])) or 'None'}, "
                lifestyle += f"Lifestyle: {patient_profile.get('lifestyle_notes', 'Standard office hours/sleep cycle')}"

            # Interaction notes (optional/future)
            interaction_notes = "Standard clinical timing guidelines apply."

            prompt = MEDICATION_SCHEDULE_PROMPT.format(
                medications=meds_str,
                lifestyle=lifestyle,
                interaction_notes=interaction_notes
            )

            response = llm.invoke([
                SystemMessage(content="You are a clinical pharmacist AI. Generate a clear, safe, and practical medication schedule."),
                HumanMessage(content=prompt)
            ])

            out_content = response.content
            if isinstance(out_content, list):
                out_content = " ".join([c.get("text", "") for c in out_content if isinstance(c, dict)])
            elif not isinstance(out_content, str):
                out_content = str(out_content)

            return out_content if out_content else "Could not generate schedule text."

        except Exception as e:
            logger.exception("AI Schedule generation failed: %s", e)
            return f"Technical error generating schedule: {str(e)}"
