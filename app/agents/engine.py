"""A small workflow engine: plan, resolve, execute, validate, explain."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.graph.dependency_graph import build_dependency_graph
from app.search.resolver import resolve_target
from app.tools import graph_tools
from app.comparison.workbook_comparator import compare_metric
from app.ingestion.workbook_indexer import load_workbook_index
from .ai_orchestrator import AIOrchestrator


def answer_query(indexes_dir: str | Path, workbook_id: str, question: str, comparison_workbook_id: str | None = None, orchestrator: AIOrchestrator | None = None) -> dict[str, Any]:
    """Answer the five planned query types from workbook evidence only."""
    index = load_workbook_index(workbook_id, indexes_dir)
    agent = orchestrator or AIOrchestrator()
    summary = {"workbook_id": index["workbook_id"], "sheets": index["sheet_names"]}
    plan = agent.plan(question, summary)
    if agent.should_escalate(plan):
        plan = agent.improve_plan(question, summary, plan)
    intent = plan["intent"]
    if plan["needs_clarification"]:
        return {"status": "needs_clarification", "intent": intent, "answer": None, "clarification": plan["clarification_question"] or "Please specify the metric.", "candidates": [], "evidence": [], "plan": plan}
    resolution = resolve_target(plan["target_text"], index, agent)
    if resolution["status"] != "resolved":
        return {"status": resolution["status"], "intent": intent, "answer": None, "clarification": "Specify a cell reference or choose a candidate.", "candidates": resolution["candidates"], "evidence": [], "plan": plan}
    graph = build_dependency_graph(index)
    node_id = resolution["node_id"]
    if node_id not in graph:
        return {"status": "unresolved", "intent": intent, "answer": None, "clarification": "The resolved label does not identify a populated metric cell.", "candidates": [], "evidence": [], "plan": plan}
    if intent == "value":
        result = graph_tools.metric_value(graph, node_id)
        evidence = result["evidence"]
    elif intent == "explain":
        result = graph_tools.direct_dependencies(graph, node_id)
        evidence = [graph_tools.node_context(graph, node_id), *result]
    elif intent == "inputs":
        result = graph_tools.upstream_inputs(graph, node_id)
        evidence = result
    elif intent == "impact":
        result = graph_tools.downstream_impacts(graph, node_id)
        evidence = result
    else:
        if not comparison_workbook_id:
            return {"status": "needs_clarification", "intent": intent, "answer": None, "clarification": "Select a second workbook to compare.", "candidates": [], "evidence": [], "plan": plan}
        comparison_index = load_workbook_index(comparison_workbook_id, indexes_dir)
        result = compare_metric(graph, build_dependency_graph(comparison_index), node_id)
        evidence = [result]
    answer = agent.explain(question, plan, evidence)
    return {"status": "ok", "intent": intent, "target": node_id, "answer": answer, "result": result, "evidence": evidence, "warnings": _validate_evidence(evidence), "plan": plan}


def _validate_evidence(evidence: list[dict[str, Any]]) -> list[str]:
    return ["No workbook evidence was returned."] if not evidence else []
