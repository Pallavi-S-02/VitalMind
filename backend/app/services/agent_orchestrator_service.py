"""
agent_orchestrator_service.py — Service layer wrapping the LangGraph orchestrator.

This is the single entry point the Flask chat API calls. It:
  1. Rebuilds a proper LangChain message list from the incoming payload
  2. Loads session state from Redis (ContextManager)
  3. Invokes the compiled orchestrator graph
  4. Persists the updated session back to Redis
  5. Returns the standardized response dict

Specialist dispatch
-------------------
`dispatch_to_specialist` is called by specialist stub nodes inside the graph.
As each real agent is built (Steps 9-13), replace the stub with a real import here.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app.agents.memory.context_manager import ContextManager

logger = logging.getLogger(__name__)

# Map of intent → specialist agent module import path (populated as agents are built)
_SPECIALIST_REGISTRY: dict[str, Any] = {}


def register_specialist(intent: str, agent_callable):
    """
    Register a specialist agent callable for a given intent.
    Call this from each agent module's __init__ or from the app factory.

    Example (once SymptomAnalystAgent is built):
        from app.agents.symptom_analyst import SymptomAnalystAgent
        register_specialist("symptom_check", SymptomAnalystAgent())
    """
    _SPECIALIST_REGISTRY[intent] = agent_callable
    logger.info("OrchestratorService: registered specialist for intent '%s'", intent)


class OrchestratorService:
    """Flask-level service for invoking the LangGraph orchestrator."""

    @staticmethod
    def process_message(
        message: str,
        patient_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Primary public method — processes a single patient message end-to-end.

        Parameters
        ----------
        message    : The raw patient text (or transcribed voice)
        patient_id : UUID of the authenticated patient (may be None for anonymous)
        session_id : Existing session ID to continue; creates new if None

        Returns
        -------
        Standardized response dict:
        {
            "response"  : str,    # Agent's reply text
            "intent"    : str,    # Classified intent
            "urgency"   : str,    # "routine" | "urgent" | "emergency"
            "session_id": str,
            "metadata"  : dict,
        }
        """
        from app.agents.orchestrator import get_compiled_graph

        # Ensure a session ID exists
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info("OrchestratorService: new session %s", session_id)

        # Load existing conversation from Redis
        ctx_manager = ContextManager(session_id)
        session_state = ctx_manager.load()

        # Convert stored messages to LangChain message objects
        lc_messages = _deserialize_messages(session_state.get("messages", []))

        # Append the new human message
        lc_messages.append(HumanMessage(content=message))

        # Build initial graph state
        initial_state = {
            "messages": lc_messages,
            "patient_id": patient_id,
            "session_id": session_id,
            "intent": None,
            "context": session_state.get("context", {}),
            "tool_outputs": [],
            "final_response": None,
            "error": None,
        }

        # Run the orchestrator graph
        try:
            graph = get_compiled_graph()
            final_state = graph.invoke(
                initial_state,
                config={"recursion_limit": 25},
            )
        except Exception as exc:
            logger.exception("OrchestratorService: graph.invoke failed: %s", exc)
            return _error_response(session_id, patient_id, str(exc))

        # Extract the formatted output
        result = final_state.get("final_response") or {}
        if isinstance(result, str):
            result = {"response": result, "intent": "unknown", "urgency": "routine"}

        # Persist updated conversation back to Redis
        assistant_reply = result.get("response", "")
        updated_messages = _serialize_messages(lc_messages) + [
            {"role": "assistant", "content": assistant_reply}
        ]
        ctx_manager.save({
            "messages": updated_messages,
            "context": final_state.get("context", {}),
            "intent": final_state.get("intent"),
            "tool_outputs": final_state.get("tool_outputs", []),
        })

        return {
            "response": result.get("response", assistant_reply),
            "intent": final_state.get("intent", "unknown"),
            "urgency": result.get("urgency", "routine"),
            "session_id": session_id,
            "metadata": result.get("metadata", {}),
        }

    @staticmethod
    def stream_process_message(
        message: str,
        patient_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """
        Generator alternative to process_message.
        Uses LangGraph's native streaming capabilities to yield live text chunks,
        and finally yields the processed output context so the UI has full state.
        
        Yields:
          dict: {"type": "chunk", "content": "..."}
          dict: {"type": "complete", "data": {"response": "...", "intent": "...", "urgency": "...", "metadata": {}}}
          dict: {"type": "error", "detail": "..."}
        """
        from app.agents.orchestrator import get_compiled_graph
        from langchain_core.messages import AIMessageChunk

        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info("OrchestratorService(stream): new session %s", session_id)

        # Load existing conversation
        ctx_manager = ContextManager(session_id)
        session_state = ctx_manager.load()
        lc_messages = _deserialize_messages(session_state.get("messages", []))
        lc_messages.append(HumanMessage(content=message))

        initial_state = {
            "messages": lc_messages,
            "patient_id": patient_id,
            "session_id": session_id,
            "intent": None,
            "context": session_state.get("context", {}),
            "tool_outputs": [],
            "final_response": None,
            "error": None,
        }

        try:
            graph = get_compiled_graph()
            final_state = initial_state
            
            # stream_mode=["messages", "values"] yields tuples (event_type, payload)
            for event_type, payload in graph.stream(
                initial_state,
                config={"recursion_limit": 25},
                stream_mode=["messages", "values"]
            ):
                if event_type == "messages":
                    chunk, metadata = payload
                    # We stream chunks that are AIMessageChunks lacking tool calls (final output)
                    if isinstance(chunk, AIMessageChunk) and chunk.content and not chunk.tool_calls:
                        # Only stream nodes that we consider "user facing". The orchestrator node is usually the final speaker.
                        yield {"type": "chunk", "content": chunk.content}
                elif event_type == "values":
                    # Update our reference to the latest state
                    final_state = payload
            
            # Streaming has concluded. Save to memory using the accumulated final_state.
            result = final_state.get("final_response") or {}
            if isinstance(result, str):
                result = {"response": result, "intent": "unknown", "urgency": "routine"}

            # Save to redis
            assistant_reply = result.get("response", "")
            updated_messages = _serialize_messages(lc_messages) + [
                {"role": "assistant", "content": assistant_reply}
            ]
            ctx_manager.save({
                "messages": updated_messages,
                "context": final_state.get("context", {}),
                "intent": final_state.get("intent"),
                "tool_outputs": final_state.get("tool_outputs", []),
            })

            yield {
                "type": "complete",
                "data": {
                    "response": assistant_reply,
                    "intent": final_state.get("intent", "unknown"),
                    "urgency": result.get("urgency", "routine"),
                    "session_id": session_id,
                    "metadata": result.get("metadata", {}),
                }
            }
            
        except Exception as exc:
            logger.exception("OrchestratorService stream failed: %s", exc)
            yield {"type": "error", "detail": str(exc)}
            return

    @staticmethod
    def dispatch_to_specialist(intent: str, state: dict) -> dict:
        """
        Called by specialist stub nodes inside the orchestrator graph.
        If a real agent is registered for this intent, invokes it.
        Otherwise returns the state unchanged (graceful degradation).
        """
        agent = _SPECIALIST_REGISTRY.get(intent)
        if agent is None:
            logger.info("OrchestratorService: no specialist registered for '%s' (stub mode)", intent)
            return state

        try:
            return agent.invoke(state)
        except Exception as exc:
            logger.error("OrchestratorService: specialist '%s' failed: %s", intent, exc)
            state["error"] = str(exc)
            return state


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_messages(messages: list) -> list[dict]:
    """Convert LangChain message objects → plain dicts for Redis storage."""
    serialized = []
    for m in messages:
        if isinstance(m, HumanMessage):
            serialized.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            serialized.append({"role": "assistant", "content": m.content})
        elif isinstance(m, SystemMessage):
            serialized.append({"role": "system", "content": m.content})
        elif isinstance(m, dict):
            serialized.append(m)
    return serialized


def _deserialize_messages(messages: list[dict]) -> list:
    """Convert plain dicts from Redis → LangChain message objects."""
    lc_messages = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        elif role == "system":
            lc_messages.append(SystemMessage(content=content))
    return lc_messages


def _error_response(session_id: str, patient_id: Optional[str], error: str) -> dict:
    return {
        "response": "I'm sorry, I encountered an unexpected issue. Please try again in a moment.",
        "intent": "error",
        "urgency": "routine",
        "session_id": session_id,
        "metadata": {"error": error, "patient_id": patient_id},
    }
