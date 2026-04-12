"""
report_reader.py — Phase 2 Vision Agent LangGraph Pipeline
Responsible for grabbing a MedicalReport, hitting MinIO for bytes, hitting GPT-4o Vision, and saving structured results.
"""

import json
import logging
from typing import Any, Literal, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_GEMINI_MODEL = "gemini-3.1-pro-preview"
_GOOGLE_KEY = __import__("os").getenv("GOOGLE_API_KEY")
from langgraph.graph import StateGraph, END, START

def _flatten_content(content) -> str:
    """Flatten Gemini list-based content blocks into a plain string."""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts).strip()
    return str(content).strip()

def _parse_llm_json(text) -> dict:
    """Helper to safely extract JSON from LLM markdown blocks. Accepts str or list."""
    t = _flatten_content(text)
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return json.loads(t.strip())


from app.models.db import db
from app.models.report import MedicalReport
from app.agents.base_agent import AgentState, BaseAgent
from app.integrations.s3_client import s3_client
from app.agents.tools.report_parsing import convert_bytes_to_base64_images
from app.agents.prompts.report_prompts import VISION_PARSING_PROMPT, CLINICAL_SUMMARY_PROMPT
from app.agents.tools.patient_history import get_patient_history

logger = logging.getLogger(__name__)

class ReportReaderState(AgentState):
    """Extends standard state for report processing pipeline"""
    report_id: str
    report: Any  # SQLAlchemy model instance OR dictionary reference
    raw_images_b64: List[str]
    lab_results_json: Any
    history_context: str
    summaries: dict

class ReportReaderAgent(BaseAgent):
    """
    Background-running agent. Doesn't route to the chat flow directly.
    Triggered async when a patient uploads a lab report.
    """
    
    def get_tools(self) -> list:
        return [get_patient_history]

    def build_graph(self) -> StateGraph:
        graph = StateGraph(ReportReaderState)
        
        graph.add_node("ingest_report", self._ingest_report)
        graph.add_node("analyze_vision", self._analyze_vision)
        graph.add_node("correlate_history", self._correlate_history)
        graph.add_node("generate_summaries", self._generate_summaries)
        graph.add_node("save_to_db", self._save_to_db)
        
        graph.add_edge(START, "ingest_report")
        
        # Conditional edge: Only proceed if MinIO fetch was successful
        graph.add_conditional_edges(
            "ingest_report", 
            self._route_after_ingest,
            {
                "analyze_vision": "analyze_vision",
                "__end__": END
            }
        )
        
        graph.add_edge("analyze_vision", "correlate_history")
        graph.add_edge("correlate_history", "generate_summaries")
        graph.add_edge("generate_summaries", "save_to_db")
        graph.add_edge("save_to_db", END)
        
        return graph

    # ========================== NODE IMPLEMENTATIONS ==========================
    
    def _ingest_report(self, state: ReportReaderState) -> ReportReaderState:
        """Load from DB, fetch bytes from MinIO, convert to base64 images"""
        report_id = state.get("report_id")
        if not report_id:
            logger.error("ReportReader: No report_id provided in state")
            return {**state, "error": "No report_id"}
            
        try:
            report = db.session.query(MedicalReport).get(report_id)
            if not report:
                return {**state, "error": f"Report {report_id} not found in DB"}
                
            # Fetch bytes from S3
            file_bytes = s3_client.get_file_bytes(report.file_url)
            if not file_bytes:
                return {**state, "error": "Failed to retrieve object from S3"}
                
            # Convert to displayable base64 components
            images_b64 = convert_bytes_to_base64_images(file_bytes, report.title)
            if not images_b64:
                return {**state, "error": "Unsupported file format or extraction failed"}
                
            return {**state, "report": report, "raw_images_b64": images_b64}
            
        except Exception as e:
            logger.exception("ReportReader ingest error: %s", e)
            return {**state, "error": str(e)}

    def _route_after_ingest(self, state: ReportReaderState) -> Literal["analyze_vision", "__end__"]:
        if state.get("error"):
            # Mark it failed in DB before ending
            self._fail_report(state)
            return "__end__"
        return "analyze_vision"

    def _analyze_vision(self, state: ReportReaderState) -> ReportReaderState:
        """Hit GPT-4o-Vision to extract strictly formatted JSON lab values"""
        images = state.get("raw_images_b64", [])
        
        # Construct message content array (1 text, N images)
        content_items = [{"type": "text", "text": "Extract all numerical lab results from these pages as requested."}]
        for b64 in images:
            content_items.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"}
            })
            
        messages = [
            HumanMessage(content=VISION_PARSING_PROMPT),
            HumanMessage(content=content_items)
        ]
        
        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0.0,
                google_api_key=_GOOGLE_KEY
            )
            response = llm.invoke(messages)
            raw_content = _flatten_content(response.content)
            lab_json = _parse_llm_json(raw_content)
            
            # Post validation/cleanup
            results = lab_json.get("results", [])
            for r in results:
                # Ensure status is uppercase
                r["status"] = r.get("status", "UNKNOWN").upper()
                
            return {**state, "lab_results_json": lab_json}
            
        except Exception as e:
            logger.exception("ReportReader vision parsing failed: %s", e)
            return {**state, "error": f"Vision Parsing Error: {str(e)}"}

    def _correlate_history(self, state: ReportReaderState) -> ReportReaderState:
        """Fetch patient's previous lab trends and context"""
        if state.get("error"): return state
        
        patient_id = state.get("patient_id")
        
        try:
            history_str = get_patient_history.invoke({"patient_id": patient_id})
            # If we had pinecone RAG of past labs, we'd query it here too.
            return {**state, "history_context": history_str}
        except Exception as e:
            logger.warning("ReportReader correlate history failed: %s", e)
            return {**state, "history_context": "No context available."}

    def _generate_summaries(self, state: ReportReaderState) -> ReportReaderState:
        """Generate Clinical and Patient summaries based on extracted abnormalities"""
        if state.get("error"): return state
        
        lab_results = state.get("lab_results_json", {})
        
        try:
            llm = ChatGoogleGenerativeAI(
                model=_GEMINI_MODEL, temperature=0.2,
                google_api_key=_GOOGLE_KEY
            )
            
            prompt = CLINICAL_SUMMARY_PROMPT.format(
                patient_summary=state.get("history_context", "Unknown context"),
                lab_results_json=json.dumps(lab_results, indent=2),
                history_context="No specific longitudinal numerical trends fetched." 
            )
            
            res = llm.invoke([HumanMessage(content=prompt)])
            summaries = _parse_llm_json(_flatten_content(res.content))
            return {**state, "summaries": summaries}
            
        except Exception as e:
            logger.exception("ReportReader summary generation failed: %s", e)
            return {**state, "error": f"Summary generation failed: {str(e)}"}

    def _save_to_db(self, state: ReportReaderState) -> ReportReaderState:
        """Persist the JSON and Summaries back to the MedicalReport model"""
        if state.get("error"):
            self._fail_report(state)
            return state
            
        try:
            # We must re-fetch or use existing session object correctly
            report_id = state.get("report_id")
            report = db.session.query(MedicalReport).get(report_id)
            if not report:
                return state
                
            report.structured_data = state.get("lab_results_json", {})
            # Mark completion
            report.structured_data["status"] = "completed"
            
            summaries = state.get("summaries", {})
            report.summary = json.dumps(summaries)
            
            report.type = report.structured_data.get("report_type", report.type)
            
            db.session.commit()
            logger.info("ReportReader successfully processed and saved report %s", report_id)
            
        except Exception as e:
            logger.error("ReportReader db save failed: %s", e)
            db.session.rollback()
            self._fail_report(state)
            
        return state

    def _fail_report(self, state: ReportReaderState):
        """Helper to mark processing failed"""
        report_id = state.get("report_id")
        if not report_id: return
        try:
            err = state.get("error", "Unknown processing error")
            report = db.session.query(MedicalReport).get(report_id)
            if report:
                report.structured_data = {"status": "failed", "error": err}
                db.session.commit()
        except Exception:
            db.session.rollback()
