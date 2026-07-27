"""Evidence-first query helpers over a NetworkX workbook graph."""

from __future__ import annotations

from typing import Any
import networkx as nx


def node_context(graph: nx.DiGraph, node_id: str) -> dict[str, Any]:
    if node_id not in graph:
        raise ValueError(f"Unknown workbook node: {node_id}")
    return {"node_id": node_id, **dict(graph.nodes[node_id])}


def metric_value(graph: nx.DiGraph, node_id: str) -> dict[str, Any]:
    context = node_context(graph, node_id)
    return {"node_id": node_id, "value": context["value"], "formula": context["formula"], "evidence": [context]}


def direct_dependencies(graph: nx.DiGraph, node_id: str) -> list[dict[str, Any]]:
    return [node_context(graph, item) for item in sorted(graph.predecessors(node_id))]


def upstream_lineage(graph: nx.DiGraph, node_id: str) -> list[dict[str, Any]]:
    return [node_context(graph, item) for item in sorted(nx.ancestors(graph, node_id))]


def upstream_inputs(graph: nx.DiGraph, node_id: str) -> list[dict[str, Any]]:
    return [item for item in upstream_lineage(graph, node_id) if item["node_type"] in {"value", "reference", "range"}]


def downstream_impacts(graph: nx.DiGraph, node_id: str) -> list[dict[str, Any]]:
    return [node_context(graph, item) for item in sorted(nx.descendants(graph, node_id))]


def dependency_paths(graph: nx.DiGraph, source: str, target: str, max_paths: int = 20) -> list[list[str]]:
    return [path for _, path in zip(range(max_paths), nx.all_simple_paths(graph, source, target))]
