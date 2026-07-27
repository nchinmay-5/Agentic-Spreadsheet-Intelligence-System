from __future__ import annotations

import tempfile
import unittest
import importlib.util
from pathlib import Path

from app.graph.dependency_graph import (
    build_dependency_graph,
    get_dependency_paths,
    get_downstream_impacts,
    get_metric_lineage,
    get_upstream_dependencies,
    graph_to_json,
    render_dependency_graph,
    write_graph_files,
)


class DependencyGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workbook_index = {
            "workbook_id": "sample",
            "sheets": [
                {
                    "name": "Input",
                    "cells": [
                        {
                            "address": "A1",
                            "value": 10,
                            "formula": None,
                            "references": [],
                            "comment": None,
                            "fill": None,
                            "number_format": "General",
                        }
                    ],
                },
                {
                    "name": "Revenue",
                    "cells": [
                        {
                            "address": "B1",
                            "value": None,
                            "formula": "=Input!A1*2",
                            "references": ["Input!A1"],
                            "comment": None,
                            "fill": None,
                            "number_format": "General",
                        },
                        {
                            "address": "C1",
                            "value": None,
                            "formula": "=B1+1",
                            "references": ["Revenue!B1"],
                            "comment": None,
                            "fill": None,
                            "number_format": "General",
                        },
                    ],
                },
            ],
        }
        self.graph = build_dependency_graph(self.workbook_index)

    def test_builds_edges_and_metadata(self) -> None:
        self.assertEqual(
            set(self.graph.edges),
            {("Input!A1", "Revenue!B1"), ("Revenue!B1", "Revenue!C1")},
        )
        self.assertEqual(self.graph.nodes["Revenue!B1"]["formula"], "=Input!A1*2")
        self.assertEqual(self.graph.nodes["Input!A1"]["value"], 10)

    def test_traces_lineage(self) -> None:
        self.assertEqual(
            get_upstream_dependencies(self.graph, "Revenue!C1"),
            ["Input!A1", "Revenue!B1"],
        )
        self.assertEqual(
            get_downstream_impacts(self.graph, "Input!A1"),
            ["Revenue!B1", "Revenue!C1"],
        )
        self.assertEqual(
            get_dependency_paths(self.graph, "Input!A1", "Revenue!C1"),
            [["Input!A1", "Revenue!B1", "Revenue!C1"]],
        )
        self.assertEqual(
            get_metric_lineage(self.graph, "Revenue!C1")["direct_dependencies"],
            ["Revenue!B1"],
        )

    def test_expands_small_ranges_for_lineage(self) -> None:
        index = {
            "workbook_id": "ranges",
            "sheets": [{"name": "Model", "cells": [
                {"address": "A1", "value": 1, "formula": None, "references": [], "comment": None, "fill": None, "number_format": "General"},
                {"address": "A2", "value": 2, "formula": None, "references": [], "comment": None, "fill": None, "number_format": "General"},
                {"address": "B1", "value": None, "formula": "=SUM(A1:A2)", "references": ["Model!A1:A2"], "comment": None, "fill": None, "number_format": "General"},
            ]}],
        }
        graph = build_dependency_graph(index)
        self.assertIn(("Model!A1", "Model!A1:A2"), graph.edges)
        self.assertIn("Model!A2", get_upstream_dependencies(graph, "Model!B1"))

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib is optional for rendering")
    def test_exports_json_and_visualization(self) -> None:
        graph_json = graph_to_json(self.graph)
        self.assertEqual(graph_json["workbook_id"], "sample")
        self.assertEqual(len(graph_json["nodes"]), 3)

        with tempfile.TemporaryDirectory() as directory:
            image_path = render_dependency_graph(
                self.graph, Path(directory) / "dependency_graph.png"
            )
            self.assertTrue(image_path.exists())
            self.assertGreater(image_path.stat().st_size, 0)
            svg_path = render_dependency_graph(
                self.graph, Path(directory) / "dependency_graph.svg"
            )
            self.assertTrue(svg_path.exists())
            self.assertGreater(svg_path.stat().st_size, 0)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib is optional for rendering")
    def test_renders_selected_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image_path = render_dependency_graph(
                self.graph,
                Path(directory) / "lineage.png",
                focus_node="Revenue!C1",
            )
            self.assertTrue(image_path.exists())
            self.assertGreater(image_path.stat().st_size, 0)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "matplotlib is optional for rendering")
    def test_writes_graph_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = write_graph_files(self.workbook_index, directory)
            self.assertTrue(paths["json"].exists())
            self.assertTrue(paths["image"].exists())
            self.assertTrue(paths["svg"].exists())


if __name__ == "__main__":
    unittest.main()
