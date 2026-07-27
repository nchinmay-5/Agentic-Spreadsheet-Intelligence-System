"""Build, query, export, and visualize workbook dependency graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
from openpyxl.utils.cell import get_column_letter, range_boundaries


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
                reference_diagnostics=cell.get("reference_diagnostics", []),
                comment=cell.get("comment"),
                number_format=cell.get("number_format"),
            )

            if not is_formula:
                continue

            for reference in cell["references"]:
                _add_reference_node(graph, reference)
                _add_range_members(graph, reference)
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


def graph_from_json(serialized: dict[str, Any]) -> nx.DiGraph:
    """Restore a graph written by :func:`graph_to_json`."""
    graph = nx.DiGraph(workbook_id=serialized.get("workbook_id"))
    for node in serialized.get("nodes", []):
        node = dict(node)
        node_id = node.pop("id")
        graph.add_node(node_id, **node)
    for edge in serialized.get("edges", []):
        graph.add_edge(edge["source"], edge["target"])
    return graph


def load_graph(path: str | Path) -> nx.DiGraph:
    """Load a serialized graph JSON file."""
    return graph_from_json(json.loads(Path(path).read_text(encoding="utf-8")))


def render_dependency_graph(
    graph: nx.DiGraph,
    output_path: str | Path,
    max_nodes: int = 150,
    focus_node: str | None = None,
) -> Path:
    """Write a layered PNG or SVG graph snapshot of at most max_nodes nodes."""
    if max_nodes < 1:
        raise ValueError("max_nodes must be at least 1.")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except ImportError as error:
        raise RuntimeError("Graph rendering requires matplotlib. Install requirements.txt.") from error
    if focus_node is not None:
        _require_node(graph, focus_node)

    selected_nodes = _select_visual_nodes(graph, max_nodes, focus_node)
    display_graph = graph.subgraph(selected_nodes).copy()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    positions, layers = _layered_positions(display_graph)
    widest_layer = max((len(layer) for layer in layers), default=1)
    figure_width = max(10, min(32, 4 + len(layers) * 3.5))
    figure_height = max(7, min(32, 3 + widest_layer * 1.1))
    figure, axis = plt.subplots(figsize=(figure_width, figure_height))
    axis.set_title(f"Dependency graph: {graph.graph.get('workbook_id', 'workbook')}")
    axis.axis("off")

    if display_graph.number_of_nodes():
        formula_nodes = [
            node
            for node in display_graph.nodes
            if display_graph.nodes[node].get("node_type") == "formula"
        ]
        reference_nodes = [
            node for node in display_graph.nodes if node not in formula_nodes
        ]
        nx.draw_networkx_edges(
            display_graph,
            pos=positions,
            ax=axis,
            arrows=True,
            arrowsize=18,
            edge_color="#9CA3AF",
            width=1.2,
        )
        nx.draw_networkx_nodes(
            display_graph,
            pos=positions,
            nodelist=reference_nodes,
            node_color="#D7EEF0",
            edgecolors="#2A7F86",
            node_shape="s",
            node_size=2_300,
            linewidths=1.2,
            ax=axis,
        )
        nx.draw_networkx_nodes(
            display_graph,
            pos=positions,
            nodelist=formula_nodes,
            node_color="#D9E6F5",
            edgecolors="#286090",
            node_shape="o",
            node_size=2_500,
            linewidths=1.2,
            ax=axis,
        )
        nx.draw_networkx_labels(
            display_graph,
            pos=positions,
            labels={node: _display_label(node) for node in display_graph.nodes},
            font_size=8 if len(display_graph) <= 30 else 6,
            font_color="#1F2937",
            ax=axis,
        )
        axis.legend(
            handles=[
                Patch(
                    facecolor="#D7EEF0",
                    edgecolor="#2A7F86",
                    label="Input, reference, or range",
                ),
                Patch(
                    facecolor="#D9E6F5",
                    edgecolor="#286090",
                    label="Formula cell",
                ),
            ],
            loc="upper center",
            bbox_to_anchor=(0.5, -0.04),
            ncol=2,
            frameon=False,
        )

    figure.tight_layout()
    figure.savefig(destination, dpi=240, bbox_inches="tight")
    plt.close(figure)
    return destination


def write_graph_files(
    workbook_index: dict[str, Any],
    output_directory: str | Path = Path("data") / "graphs",
    max_visual_nodes: int = 150,
    focus_node: str | None = None,
) -> dict[str, Path]:
    """Build a workbook graph and write JSON, PNG, and SVG visualizations."""
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
        graph,
        destination_directory / f"{workbook_id}.png",
        max_visual_nodes,
        focus_node,
    )
    svg_path = render_dependency_graph(
        graph,
        destination_directory / f"{workbook_id}.svg",
        max_visual_nodes,
        focus_node,
    )
    return {"json": json_path, "image": image_path, "svg": svg_path}


def _select_visual_nodes(
    graph: nx.DiGraph, max_nodes: int, focus_node: str | None
) -> list[str]:
    if focus_node is not None:
        lineage = (
            {focus_node}
            | nx.ancestors(graph, focus_node)
            | nx.descendants(graph, focus_node)
        )
        return sorted(lineage, key=lambda node: (-graph.degree(node), node))[:max_nodes]

    return sorted(graph.nodes, key=lambda node: (-graph.degree(node), node))[:max_nodes]


def _layered_positions(
    graph: nx.DiGraph,
) -> tuple[dict[str, tuple[float, float]], list[list[str]]]:
    if not nx.is_directed_acyclic_graph(graph):
        return nx.spring_layout(graph, seed=42), [list(graph.nodes)]

    levels: dict[str, int] = {}
    for node in nx.topological_sort(graph):
        predecessors = list(graph.predecessors(node))
        levels[node] = max((levels[parent] + 1 for parent in predecessors), default=0)

    layers: list[list[str]] = []
    for level in range(max(levels.values(), default=0) + 1):
        layers.append(sorted(node for node, node_level in levels.items() if node_level == level))

    positions: dict[str, tuple[float, float]] = {}
    for level, layer in enumerate(layers):
        center = (len(layer) - 1) / 2
        for index, node in enumerate(layer):
            positions[node] = (float(level), center - index)
    return positions, layers


def _display_label(node_id: str) -> str:
    if "!" not in node_id:
        return node_id
    sheet_name, address = node_id.rsplit("!", maxsplit=1)
    return f"{sheet_name}!\n{address}"


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
            reference_diagnostics=[],
            comment=None,
            number_format=None,
        )


def _add_range_members(graph: nx.DiGraph, reference: str, max_cells: int = 10_000) -> None:
    """Connect manageable A1 ranges to their cells for useful lineage evidence."""
    if ":" not in reference:
        return
    sheet, address_range = reference.rsplit("!", 1)
    try:
        min_column, min_row, max_column, max_row = range_boundaries(address_range)
    except ValueError:
        return
    count = (max_column - min_column + 1) * (max_row - min_row + 1)
    if count > max_cells:
        return
    for row in range(min_row, max_row + 1):
        for column in range(min_column, max_column + 1):
            member = f"{sheet}!{get_column_letter(column)}{row}"
            _add_reference_node(graph, member)
            graph.add_edge(member, reference)


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
