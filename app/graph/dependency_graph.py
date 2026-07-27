"""Build, query, export, and visualize workbook dependency graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
import networkx as nx

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def build_dependency_graph(workbook_index: dict[str, Any]) -> nx.DiGraph:
    """Build a directed graph with precedent nodes pointing to formula nodes."""
    graph = nx.DiGraph(workbook_id=workbook_index["workbook_id"])

    for sheet in workbook_index["sheets"]:
        for cell in sheet["cells"]:
            node_id = _cell_node_id(sheet["name"], cell["address"])
            is_formula = cell["formula"] is not None
            graph.add_node(
                node_id,
                node_type="formula" if is_formula else "value",
                sheet=sheet["name"],
                address=cell["address"],
                formula=cell["formula"],
                value=cell["value"],
                references=cell["references"],
                comment=cell["comment"],
                fill=cell["fill"],
                number_format=cell["number_format"],
            )

            if not is_formula:
                continue

            for reference in cell["references"]:
                _add_reference_node(graph, reference)
                graph.add_edge(reference, node_id)

    return graph


def get_upstream_dependencies(graph: nx.DiGraph, cell: str) -> list[str]:
    """Return all transitive precedents for a cell or range node."""
    _require_node(graph, cell)
    return sorted(nx.ancestors(graph, cell))


def get_downstream_impacts(graph: nx.DiGraph, cell: str) -> list[str]:
    """Return all transitive dependent formula nodes for a cell or range node."""
    _require_node(graph, cell)
    return sorted(nx.descendants(graph, cell))


def get_dependency_paths(
    graph: nx.DiGraph, source: str, target: str, max_paths: int = 100
) -> list[list[str]]:
    """Return simple dependency paths from source to target, up to max_paths."""
    _require_node(graph, source)
    _require_node(graph, target)
    if max_paths < 1:
        raise ValueError("max_paths must be at least 1.")

    paths: list[list[str]] = []
    for path in nx.all_simple_paths(graph, source, target):
        paths.append(path)
        if len(paths) >= max_paths:
            break
    return paths


def get_metric_lineage(graph: nx.DiGraph, cell: str) -> dict[str, Any]:
    """Return direct and transitive dependency evidence for a metric node."""
    _require_node(graph, cell)
    attributes = graph.nodes[cell]
    return {
        "metric": cell,
        "formula": attributes.get("formula"),
        "direct_dependencies": sorted(graph.predecessors(cell)),
        "upstream_dependencies": get_upstream_dependencies(graph, cell),
    }


def graph_to_json(graph: nx.DiGraph, workbook_id: str | None = None) -> dict[str, Any]:
    """Convert a graph into a transparent, JSON-safe structure."""
    return {
        "workbook_id": workbook_id or graph.graph.get("workbook_id"),
        "nodes": [
            {"id": node_id, **attributes}
            for node_id, attributes in sorted(graph.nodes(data=True))
        ],
        "edges": [
            {"source": source, "target": target}
            for source, target in sorted(graph.edges())
        ],
    }


def render_dependency_graph(
    graph: nx.DiGraph, output_path: str | Path, max_nodes: int = 150
) -> Path:
    """Write a readable PNG snapshot of at most max_nodes graph nodes."""
    if max_nodes < 1:
        raise ValueError("max_nodes must be at least 1.")

    selected_nodes = list(graph.nodes)[:max_nodes]
    display_graph = graph.subgraph(selected_nodes).copy()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    figure_size = max(10, min(24, 8 + len(display_graph) / 15))
    figure, axis = plt.subplots(figsize=(figure_size, figure_size))
    axis.set_title(f"Dependency graph: {graph.graph.get('workbook_id', 'workbook')}")
    axis.axis("off")

    if display_graph.number_of_nodes():
        positions = nx.spring_layout(display_graph, seed=42)
        colors = [
            "#4C78A8"
            if display_graph.nodes[node].get("node_type") == "formula"
            else "#72B7B2"
            for node in display_graph.nodes
        ]
        nx.draw_networkx(
            display_graph,
            pos=positions,
            ax=axis,
            labels={node: node for node in display_graph.nodes},
            node_color=colors,
            node_size=1_400,
            font_size=7,
            arrows=True,
            arrowsize=16,
            edge_color="#8A8A8A",
        )

    figure.tight_layout()
    figure.savefig(destination, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return destination


def write_graph_files(
    workbook_index: dict[str, Any],
    output_directory: str | Path = Path("data") / "graphs",
    max_visual_nodes: int = 150,
) -> dict[str, Path]:
    """Build a workbook graph and write its JSON evidence and PNG visualization."""
    graph = build_dependency_graph(workbook_index)
    destination_directory = Path(output_directory)
    destination_directory.mkdir(parents=True, exist_ok=True)
    workbook_id = workbook_index["workbook_id"]

    json_path = destination_directory / f"{workbook_id}.json"
    json_path.write_text(
        json.dumps(graph_to_json(graph, workbook_id), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    image_path = render_dependency_graph(
        graph, destination_directory / f"{workbook_id}.png", max_visual_nodes
    )
    return {"json": json_path, "image": image_path}


def _add_reference_node(graph: nx.DiGraph, reference: str) -> None:
    if reference not in graph:
        graph.add_node(
            reference,
            node_type="range" if ":" in reference else "reference",
            sheet=None,
            address=None,
            formula=None,
            value=None,
            references=[],
            comment=None,
            fill=None,
            number_format=None,
        )


def _cell_node_id(sheet_name: str, address: str) -> str:
    return f"{_format_sheet_name(sheet_name)}!{address}"


def _format_sheet_name(sheet_name: str) -> str:
    simple_name = sheet_name.replace("_", "").replace(".", "")
    if simple_name.isalnum() and (sheet_name[0].isalpha() or sheet_name[0] == "_"):
        return sheet_name
    return "'" + sheet_name.replace("'", "''") + "'"


def _require_node(graph: nx.DiGraph, cell: str) -> None:
    if cell not in graph:
        raise ValueError(f"Cell or range is not present in the graph: {cell}")
