"""
orchestrator.py — VitalMind Central Agent Orchestrator (LangGraph)

Graph topology:
  START
    │
    ▼
  aggregate_context     ← Loads patient profile from Redis/Postgres
    │
    ▼
  classify_intent       ← GPT-4o function-calling: determines which specialist
    │
    ▼
  route_to_agent        ← Conditional edge → specialist stub node
    │
    ▼
  [specialist_node]     ← Placeholder nodes (replaced by real agents in Steps 9-13)
    │
    ▼
  synthesize_response   ← Merges results if multiple agents were called
    │
    ▼
  format_output         ← Converts to standard API response dict
    │
    ▼
  END
"""

from __future__ import annotations

import json
import logging
import os
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

_GEMINI_MODEL = "gemini-3.1-pro-preview"
_GOOGLE_KEY = __import__("os").getenv("GOOGLE_API_KEY")
from langgraph.graph import StateGraph, END, START

from app.agents.base_agent import AgentState
from app.agents.memory.patient_memory import PatientMemory
from app.agents.memory.context_manager import ContextManager
from app.agents.prompts.system_prompts import PROMPTS

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Intent classification function schema (OpenAI function calling)
# ─────────────────────────────────────────────────────────────────────────────

INTENT_CLASSIFIER_SCHEMA = {
    "name": "classify_patient_intent",
    "description": (
        "Classify the patient's message into the correct specialist intent category. "
        "Choose the single most appropriate category."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "symptom_check",
                    "report_analysis",
                    "triage",
                    "voice_interaction",
                    "drug_interaction",
                    "monitoring_query",
                    "care_plan",
                    "patient_search",
                    "general_question",
                ],
                "description": "The classified intent for this patient message. Use 'patient_search' if the user is asking about a specific person or searching for a patient record.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence score 0-1 for the classification. Be conservative.",
            },
            "reasoning": {
                "type": "string",
                "description": "Short explanation for selecting this intent.",
            },
            "is_emergency": {
                "type": "boolean",
                "description": "True if this message describes an immediate medical emergency.",
            },
        },
        "required": ["intent", "confidence", "reasoning", "is_emergency"],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Node functions
# ─────────────────────────────────────────────────────────────────────────────


def aggregate_context(state: AgentState) -> AgentState:
    """
    Node 1 — Fetch patient profile from Redis/PostgreSQL and inject into state.
    Skips gracefully if patient_id is not provided (unauthenticated context).
    """
    patient_id = state.get("patient_id")
    context = state.get("context", {})

    if patient_id:
        try:
            memory = PatientMemory(patient_id)
            patient_ctx = memory.load()
            context = {**context, "patient": patient_ctx}
            logger.info("Orchestrator: patient context loaded for %s", patient_id)
        except Exception as exc:
            logger.warning("Orchestrator: could not load patient context: %s", exc)
            context = {**context, "patient": {}}
    else:
        logger.debug("Orchestrator: no patient_id — skipping context aggregation.")

    return {**state, "context": context}


def classify_intent(state: AgentState) -> AgentState:
    """
    Node 2 — Use GPT-4o with function calling to classify the patient message.

    Immediately overrides to 'triage' if an emergency is detected.
    """
    messages = state.get("messages", [])
    patient_ctx = state.get("context", {}).get("patient", {})

    # Build a compact patient summary for the classifier prompt
    patient_summary = (
        f"Name: {patient_ctx.get('name', 'Unknown')}, "
        f"Conditions: {', '.join(patient_ctx.get('chronic_conditions', [])) or 'None known'}, "
        f"Medications: {', '.join(patient_ctx.get('current_medications', []) if isinstance(patient_ctx.get('current_medications', []), list) else [m.get('name', '') for m in patient_ctx.get('current_medications', [])]) or 'None'}"
    )

    system_content = PROMPTS["orchestrator"].format(patient_context=patient_summary) if "{patient_context}" in PROMPTS["orchestrator"] else PROMPTS["orchestrator"]

    classifier_messages = [
        SystemMessage(content=system_content),
        *messages,
    ]

    try:
        llm = ChatGoogleGenerativeAI(
            model=_GEMINI_MODEL, temperature=0,
            google_api_key=_GOOGLE_KEY
        )
        # Gemini function calling via bind_tools — schema is identical to OpenAI tool format
        llm_with_tools = llm.bind_tools([INTENT_CLASSIFIER_SCHEMA], tool_choice="any")

        response = llm_with_tools.invoke(classifier_messages)

        # Extract the function call arguments
        tool_calls = getattr(response, "tool_calls", []) or []
        if tool_calls:
            args = tool_calls[0].get("args", {})
        else:
            # Fallback: try parsing content if no tool call
            args = {"intent": "general_question", "confidence": 0.5, "reasoning": "Fallback", "is_emergency": False}

        intent = args.get("intent", "general_question")
        is_emergency = args.get("is_emergency", False)

        # Emergency override — jump to triage immediately
        if is_emergency:
            intent = "triage"
            logger.warning("Orchestrator: EMERGENCY detected — overriding intent to 'triage'")

        logger.info(
            "Orchestrator: classified intent='%s' confidence=%.2f emergency=%s",
            intent, args.get("confidence", 0), is_emergency,
        )

        tool_outputs = list(state.get("tool_outputs", []))
        tool_outputs.append({
            "node": "classify_intent",
            "intent": intent,
            "confidence": args.get("confidence"),
            "reasoning": args.get("reasoning"),
            "is_emergency": is_emergency,
        })

        return {**state, "intent": intent, "tool_outputs": tool_outputs}

    except Exception as exc:
        logger.error("Orchestrator: intent classification failed: %s", exc)
        return {**state, "intent": "general_question", "error": str(exc)}


def route_to_agent(state: AgentState) -> Literal[
    "symptom_check",
    "report_analysis",
    "triage",
    "voice_interaction",
    "drug_interaction",
    "monitoring_query",
    "care_plan",
    "general_question",
]:
    """
    Conditional edge — reads classified intent and routes to the correct specialist node.
    This is a pure routing function, not a state-modifying node.
    """
    intent = state.get("intent", "general_question")
    logger.info("Orchestrator: routing to specialist node '%s'", intent)
    return intent


# ─────────────────────────────────────────────────────────────────────────────
# Specialist stub nodes
# (These will be replaced by real agents in Steps 9–13)
# ─────────────────────────────────────────────────────────────────────────────

def _specialist_stub(agent_name: str, state: AgentState) -> AgentState:
    """Generic stub: invokes the specialist agent service if available, else returns a graceful placeholder."""
    try:
        from app.services.agent_orchestrator_service import OrchestratorService
        result = OrchestratorService.dispatch_to_specialist(agent_name, state)
        return result
    except ImportError:
        pass
    except Exception as exc:
        logger.error("Orchestrator: specialist '%s' raised: %s", agent_name, exc)

    # Graceful degradation — inform user while agent is still being built
    return {
        **state,
        "tool_outputs": list(state.get("tool_outputs", [])) + [
            {"node": agent_name, "status": "stub", "message": f"{agent_name} agent coming soon"}
        ],
    }


def node_symptom_check(state: AgentState) -> AgentState:
    return _specialist_stub("symptom_check", state)

def node_report_analysis(state: AgentState) -> AgentState:
    return _specialist_stub("report_analysis", state)

def node_triage(state: AgentState) -> AgentState:
    """
    Triage node: ESI 1–5 evaluation using the TriageAgent LangGraph.
    Priority path — uses gpt-4o-mini for sub-2s response.
    Falls back to a direct LLM call if the agent is not yet compiled.
    """
    logger.critical("Orchestrator: TRIAGE node activated for patient %s", state.get("patient_id"))

    # ── Primary path: dispatch to registered TriageAgent specialist ──────
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""

    try:
        from app.services.agent_orchestrator_service import OrchestratorService
        result = OrchestratorService.dispatch_to_specialist("triage", state)
        # If the specialist handler set a final_response, use it
        if result.get("final_response"):
            return result
    except Exception as exc:
        logger.warning("Orchestrator: TriageAgent specialist dispatch failed: %s — using fallback", exc)

    # ── Fallback: invoke run_triage convenience function directly ────────
    try:
        from app.agents.triage_agent import run_triage
        from app.agents.memory.patient_memory import PatientMemory

        patient_id = state.get("patient_id")
        patient_context = state.get("context", {}).get("patient", {})

        # Load patient context if not already available
        if patient_id and not patient_context:
            try:
                memory = PatientMemory(patient_id)
                patient_context = memory.load()
            except Exception:
                patient_context = {}

        result = run_triage(
            chief_complaint=last_message,
            patient_id=patient_id,
            vital_signs=state.get("context", {}).get("vital_signs"),
            patient_context=patient_context,
            session_id=state.get("session_id"),
        )

        return {**state, "final_response": result}

    except Exception as exc:
        logger.error("Orchestrator: TriageAgent fallback also failed: %s", exc)

    # ── Last resort: direct LLM ──────────────────────────────────────────
    try:
        llm = ChatGoogleGenerativeAI(
            model=_GEMINI_MODEL, temperature=0,
            google_api_key=_GOOGLE_KEY
        )
        triage_response = llm.invoke([
            SystemMessage(content=PROMPTS["triage"]),
            HumanMessage(content=last_message),
        ])
        response_text = triage_response.content
    except Exception as exc:
        logger.error("Triage node LLM call failed: %s", exc)
        response_text = (
            "⚠️ EMERGENCY ALERT: Based on your description, please call 911 or your local emergency number "
            "IMMEDIATELY. Do not wait. If you cannot call, ask someone nearby to call for you."
        )

    return {**state, "final_response": {"type": "triage", "content": response_text, "urgency": "emergency"}}


def node_voice_interaction(state: AgentState) -> AgentState:
    return _specialist_stub("voice_interaction", state)

def node_drug_interaction(state: AgentState) -> AgentState:
    return _specialist_stub("drug_interaction", state)

def node_monitoring_query(state: AgentState) -> AgentState:
    return _specialist_stub("monitoring_query", state)

def node_care_plan(state: AgentState) -> AgentState:
    return _specialist_stub("care_plan", state)

def node_patient_search(state: AgentState) -> AgentState:
    """
    Search for a patient by name or ID using the SearchService.
    Useful for doctors asking about specific patients.
    """
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    
    from app.services.search_service import SearchService
    
    # 1. Ask Gemini to extract the name or keywords for searching
    try:
        llm = ChatGoogleGenerativeAI(model=_GEMINI_MODEL, temperature=0, google_api_key=_GOOGLE_KEY)
        extract_prompt = f"Extract the patient name or search keywords from this physician query: '{last_message}'. Return ONLY the name/keywords."
        name_response = llm.invoke([HumanMessage(content=extract_prompt)])
        search_query = name_response.content.strip() or last_message
    except Exception:
        search_query = last_message

    # 2. Query ElasticSearch
    try:
        results = SearchService.global_search(query=search_query, limit=5)
        # Filter for patients
        patient_results = [r for r in results if r.get("document_type") == "patient"]
        
        if not patient_results:
            return {
                **state, 
                "final_response": {
                    "type": "patient_search", 
                    "content": f"I couldn't find any patient matching '{search_query}'. Please double-check the spelling or try a more specific search."
                }
            }

        # 3. Handle multiple vs single matches
        if len(patient_results) > 1:
            match_list = "\n".join([f"- {r.get('first_name', '')} {r.get('last_name', '')} ({r.get('id')[:8]}...)" for r in patient_results])
            return {
                **state,
                "final_response": {
                    "type": "patient_search",
                    "content": f"I found several patients matching your query. Which one did you mean?\n\n{match_list}"
                }
            }

        # 4. Single match — synthesized summary
        target = patient_results[0]
        full_name = f"{target.get('first_name', '')} {target.get('last_name', '')}"
        
        # Load the real patient memory for synthesis if match found
        from app.agents.memory.patient_memory import PatientMemory
        found_memory = PatientMemory(target.get("id")).load()
        
        # We don't overwrite state['patient_id'] or state['context'] to avoid session confusion,
        # we just pass the found data to the LLM.
        
        llm_response = llm.invoke([
            SystemMessage(content=(
                "You are the VitalMind Clinical Copilot. Summarize the patient record below for a physician. "
                "Include: Essential profile, major conditions, recent vitals, and core medications. "
                "Use a professional, concise tone."
            )),
            HumanMessage(content=f"Patient Record for {full_name}:\n{json.dumps(found_memory, indent=2)}")
        ])

        return {
            **state,
            "final_response": {
                "type": "patient_search",
                "content": llm_response.content,
                "metadata": {"patient_id": target.get("id"), "found_name": full_name}
            }
        }

    except Exception as exc:
        logger.error("node_patient_search failed: %s", exc)
        return {**state, "final_response": "I encountered an error while searching the patient directory."}


def node_general_question(state: AgentState) -> AgentState:
    """General health Q&A — answered directly by GPT-4o."""
    messages = state.get("messages", [])
    try:
        llm = ChatGoogleGenerativeAI(
            model=_GEMINI_MODEL, temperature=0.3,
            google_api_key=_GOOGLE_KEY
        )
        response = llm.invoke([
            SystemMessage(content=(
                "You are VitalMind, a knowledgeable and compassionate AI health assistant. "
                "Answer the patient's question clearly and helpfully. "
                "Always recommend consulting a healthcare professional for medical decisions."
            )),
            *messages,
        ])
        final = {"type": "general_question", "content": response.content}
    except Exception as exc:
        logger.error("General question node failed: %s", exc)
        final = {"type": "general_question", "content": "I'm sorry, I encountered an issue. Please try again."}

    return {**state, "final_response": final}


# ─────────────────────────────────────────────────────────────────────────────
# Post-routing nodes
# ─────────────────────────────────────────────────────────────────────────────

def synthesize_response(state: AgentState) -> AgentState:
    """
    Node — Merges tool_outputs if multiple agents contributed.
    For single-agent flows the final_response is already set by the specialist.
    """
    if state.get("final_response"):
        # Specialist already set a full response — pass through
        return state

    # Aggregate any tool outputs into a coherent response
    tool_outputs = state.get("tool_outputs", [])
    combined = "\n\n".join(
        o.get("message", o.get("content", str(o)))
        for o in tool_outputs
        if o.get("node") not in ("classify_intent",)
    )
    return {
        **state,
        "final_response": {
            "type": state.get("intent", "unknown"),
            "content": combined or "I processed your request. Please let me know if you need more help.",
        },
    }


def format_output(state: AgentState) -> AgentState:
    """
    Node — Adds metadata envelope around the final response, ready for the API layer.
    """
    raw = state.get("final_response") or {}
    if isinstance(raw, str):
        raw = {"type": "unknown", "content": raw}

    out_content = raw.get("content", "")
    if isinstance(out_content, list):
        out_content = " ".join([c.get("text", "") for c in out_content if isinstance(c, dict)])
    elif not isinstance(out_content, str):
        out_content = str(out_content)

    formatted = {
        "response": out_content,
        "intent": state.get("intent"),
        "urgency": raw.get("urgency", "routine"),
        "session_id": state.get("session_id"),
        "patient_id": state.get("patient_id"),
        "metadata": {
            "tool_outputs": state.get("tool_outputs", []),
            "error": state.get("error"),
        },
    }
    return {**state, "final_response": formatted}


# ─────────────────────────────────────────────────────────────────────────────
# Graph assembly
# ─────────────────────────────────────────────────────────────────────────────

def build_orchestrator_graph() -> StateGraph:
    """
    Compile and return the full orchestrator StateGraph.

    Edge map:
      START → aggregate_context → classify_intent → route_to_agent
           ↓ (conditional)
           ├─ symptom_check    → synthesize_response
           ├─ report_analysis  → synthesize_response
           ├─ triage           → synthesize_response
           ├─ voice_interaction → synthesize_response
           ├─ drug_interaction  → synthesize_response
           ├─ monitoring_query  → synthesize_response
           ├─ care_plan         → synthesize_response
           └─ general_question  → synthesize_response
                                        ↓
                                  format_output → END
    """
    graph = StateGraph(AgentState)

    # ── Core orchestration nodes ──────────────────────────────────────────
    graph.add_node("aggregate_context", aggregate_context)
    graph.add_node("classify_intent", classify_intent)

    # ── Specialist nodes ──────────────────────────────────────────────────
    graph.add_node("symptom_check", node_symptom_check)
    graph.add_node("report_analysis", node_report_analysis)
    graph.add_node("triage", node_triage)
    graph.add_node("voice_interaction", node_voice_interaction)
    graph.add_node("drug_interaction", node_drug_interaction)
    graph.add_node("monitoring_query", node_monitoring_query)
    graph.add_node("care_plan", node_care_plan)
    graph.add_node("patient_search", node_patient_search)
    graph.add_node("general_question", node_general_question)

    # ── Post-routing nodes ────────────────────────────────────────────────
    graph.add_node("synthesize_response", synthesize_response)
    graph.add_node("format_output", format_output)

    # ── Edges ─────────────────────────────────────────────────────────────
    graph.add_edge(START, "aggregate_context")
    graph.add_edge("aggregate_context", "classify_intent")

    # Conditional routing after intent classification
    graph.add_conditional_edges(
        "classify_intent",
        route_to_agent,
        {
            "symptom_check": "symptom_check",
            "report_analysis": "report_analysis",
            "triage": "triage",
            "voice_interaction": "voice_interaction",
            "drug_interaction": "drug_interaction",
            "monitoring_query": "monitoring_query",
            "care_plan": "care_plan",
            "patient_search": "patient_search",
            "general_question": "general_question",
        },
    )

    # All specialist nodes flow into synthesis
    for specialist in [
        "symptom_check", "report_analysis", "triage", "voice_interaction",
        "drug_interaction", "monitoring_query", "care_plan", "patient_search", "general_question",
    ]:
        graph.add_edge(specialist, "synthesize_response")

    graph.add_edge("synthesize_response", "format_output")
    graph.add_edge("format_output", END)

    return graph


# Compile once at module load — reused across all requests
_compiled_graph = None

def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_orchestrator_graph().compile()
        logger.info("Orchestrator graph compiled and cached.")
    return _compiled_graph
