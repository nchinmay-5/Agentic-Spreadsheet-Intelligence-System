"""Optional LangGraph wrapper around the deterministic query workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .engine import answer_query


class QueryState(TypedDict, total=False):
    workbook_id: str
    question: str
    comparison_workbook_id: str | None
    response: dict[str, Any]


def build_query_workflow(indexes_dir: str | Path):
    """Build one transparent execute node; routing stays inside the tested engine."""
    def execute(state: QueryState) -> QueryState:
        return {"response": answer_query(indexes_dir, state["workbook_id"], state["question"], state.get("comparison_workbook_id"))}

    workflow = StateGraph(QueryState)
    workflow.add_node("execute", execute)
    workflow.add_edge(START, "execute")
    workflow.add_edge("execute", END)
    return workflow.compile()
