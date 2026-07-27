"""Conservative comparison report; it reports changes without causal claims."""

from __future__ import annotations

from typing import Any
import networkx as nx


def compare_metric(graph_a: nx.DiGraph, graph_b: nx.DiGraph, node_id: str) -> dict[str, Any]:
    if node_id not in graph_a or node_id not in graph_b:
        raise ValueError("Metric must exist in both workbooks.")
    a, b = graph_a.nodes[node_id], graph_b.nodes[node_id]
    changed_nodes = []
    for item in sorted(nx.ancestors(graph_a, node_id) | nx.ancestors(graph_b, node_id)):
        before, after = graph_a.nodes.get(item), graph_b.nodes.get(item)
        if before != after:
            changed_nodes.append({"node_id": item, "before": before, "after": after})
    return {
        "metric": node_id,
        "before": {"value": a.get("value"), "formula": a.get("formula")},
        "after": {"value": b.get("value"), "formula": b.get("formula")},
        "value_changed": a.get("value") != b.get("value"),
        "formula_changed": a.get("formula") != b.get("formula"),
        "changed_upstream_nodes": changed_nodes,
        "warning": "Changed upstream nodes are candidates, not proof of causation.",
    }
