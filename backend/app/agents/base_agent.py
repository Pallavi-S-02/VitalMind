"""
BaseAgent — LangGraph foundation for all VitalMind agents.

Every specialist agent inherits from BaseAgent and overrides:
  - build_graph() to define nodes and edges
  - get_tools()   to register LangChain tools

Shared AgentState TypedDict provides a consistent state contract
across the entire agent graph.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


def extract_llm_text(response) -> str:
    """
    Safely extract plain text from a LangChain LLM response.

    Gemini 3.1 Pro (thinking mode) returns response.content as a list:
        [{'type': 'text', 'text': '```json\\n{...}\\n```', 'extras': {'signature': ...}}]

    Older/simpler models return a plain str.
    This helper normalises both and strips markdown code fences.

    Import as:
        from app.agents.base_agent import extract_llm_text
        text = extract_llm_text(response)
        result = json.loads(text)
    """
    import re as _re
    content = response.content

    # Normalise list → str  (Gemini thinking-mode)
    if isinstance(content, list):
        parts = [
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
            if (isinstance(item, dict) and item.get("type") == "text") or not isinstance(item, dict)
        ]
        content = "".join(parts).strip()

    if not isinstance(content, str):
        content = str(content)

    # Strip markdown JSON fences: ```json ... ``` or ``` ... ```
    content = _re.sub(r"^```(?:json)?\s*\n?", "", content.strip(), flags=_re.IGNORECASE)
    content = _re.sub(r"\n?```\s*$", "", content.strip())
    return content.strip()



# ---------------------------------------------------------------------------
# Shared state contract
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    """
    Shared state object threaded through every LangGraph node.

    Fields
    ------
    messages        : Conversation history (LangChain message objects)
    patient_id      : UUID of the authenticated patient
    session_id      : Unique ID for the current interaction session
    intent          : Classified intent string (e.g. "symptom_check")
    context         : Arbitrary dict of enriched context (patient history, etc.)
    tool_outputs    : Accumulated outputs from LangChain tool nodes
    final_response  : Formatted string/dict ready for the API response layer
    error           : Optional error message if a node fails
    """
    messages: list[BaseMessage]
    patient_id: Optional[str]
    session_id: Optional[str]
    intent: Optional[str]
    context: dict[str, Any]
    tool_outputs: list[dict[str, Any]]
    final_response: Optional[str | dict]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------

class BaseAgent(ABC):
    """
    Abstract base class for all VitalMind LangGraph agents.

    Each concrete agent must implement:
      - build_graph()  → StateGraph  : define the node/edge topology
      - get_tools()    → list        : return LangChain-compatible tools

    Usage
    -----
        class MyAgent(BaseAgent):
            def build_graph(self):
                ...
            def get_tools(self):
                return [my_tool_fn]

        agent = MyAgent(model="gpt-4o", temperature=0)
        result = agent.invoke({"messages": [...], "patient_id": "..."})
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0,
        streaming: bool = False,
    ) -> None:
        self.model_name = model
        self.temperature = temperature
        self.streaming = streaming

        # Build the LLM — tools are bound lazily inside build_graph()
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            streaming=streaming,
            google_api_key=__import__("os").getenv("GOOGLE_API_KEY"),
            
        )

        # Compile the graph
        self._graph = self._compile()

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def build_graph(self) -> StateGraph:
        """
        Construct and return the LangGraph StateGraph.
        Subclasses add nodes with:
            graph = StateGraph(AgentState)
            graph.add_node("my_node", self._my_node_fn)
            graph.set_entry_point("my_node")
            graph.add_edge("my_node", END)
            return graph
        """

    @abstractmethod
    def get_tools(self) -> list:
        """Return the list of LangChain @tool functions for this agent."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def invoke(
        self,
        input_state: dict[str, Any],
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Execute the agent graph synchronously.

        Parameters
        ----------
        input_state : Initial state dictionary (must match AgentState fields)
        config      : Optional LangGraph RunnableConfig (e.g. recursion_limit)

        Returns
        -------
        Final state dictionary after graph execution.
        """
        config = config or {}
        try:
            logger.info(
                "Agent %s invoked | session=%s patient=%s",
                self.__class__.__name__,
                input_state.get("session_id"),
                input_state.get("patient_id"),
            )
            return self._graph.invoke(input_state, config)
        except Exception as exc:
            logger.exception("Agent %s failed: %s", self.__class__.__name__, exc)
            return {**input_state, "error": str(exc), "final_response": None}

    async def ainvoke(
        self,
        input_state: dict[str, Any],
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Async variant of invoke() for use with FastAPI/async Flask."""
        config = config or {}
        try:
            logger.info(
                "Agent %s async invoked | session=%s",
                self.__class__.__name__,
                input_state.get("session_id"),
            )
            return await self._graph.ainvoke(input_state, config)
        except Exception as exc:
            logger.exception("Agent %s async failed: %s", self.__class__.__name__, exc)
            return {**input_state, "error": str(exc), "final_response": None}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compile(self):
        """Build and compile the StateGraph (with LangGraph checkpointing stub)."""
        graph = self.build_graph()
        compiled = graph.compile()
        logger.debug("Agent %s graph compiled successfully.", self.__class__.__name__)
        return compiled

    def _bind_tools(self):
        """Return the LLM with tools bound (for tool-calling nodes)."""
        tools = self.get_tools()
        if not tools:
            return self.llm
        return self.llm.bind_tools(tools)

    @staticmethod
    def _default_state() -> AgentState:
        """Return a blank state with safe defaults."""
        return AgentState(
            messages=[],
            patient_id=None,
            session_id=None,
            intent=None,
            context={},
            tool_outputs=[],
            final_response=None,
            error=None,
        )
