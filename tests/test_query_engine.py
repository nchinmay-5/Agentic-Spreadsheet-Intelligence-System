import tempfile
from copy import deepcopy
from pathlib import Path
from unittest import TestCase

from app.agents.engine import answer_query
from app.ingestion.workbook_indexer import save_workbook_index


class FakeOrchestrator:
    def __init__(self, intent, target_text):
        self.intent = intent
        self.target_text = target_text

    def plan(self, question, workbook_summary):
        return {"intent": self.intent, "target_text": self.target_text, "input_text": None, "needs_clarification": False, "clarification_question": None, "confidence": 1.0, "requested_tools": []}

    def should_escalate(self, plan):
        return False

    def improve_plan(self, question, workbook_summary, local_plan):
        return local_plan

    def explain(self, question, plan, evidence):
        return "Evidence-grounded test answer."

    def rank_sheets(self, query, sheet_names):
        return [{"sheet": "Model", "confidence": 1.0}]

    def propose_table_ranges(self, query, sheet_context):
        return [{"range": "A1:B2", "confidence": 1.0}]

    def confirm_table(self, query, table):
        return {"is_table": True, "relevant_to_query": True, "confidence": 1.0}

    def select_table_cell(self, query, table):
        return {"cell": "B1", "confidence": 1.0}


class QueryEngineTests(TestCase):
    def setUp(self):
        self.index = {
            "workbook_id": "demo",
            "sheet_names": ["Model"],
            "sheets": [{"name": "Model", "max_row": 2, "max_column": 2, "used_range": "A1:B2", "cells": [
                {"address": "A1", "value": "Revenue", "formula": None, "references": []},
                {"address": "B1", "value": None, "formula": "=B2*2", "references": ["Model!B2"]},
                {"address": "B2", "value": 10, "formula": None, "references": []},
            ]}],
        }
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.indexes_dir = Path(self.temp_directory.name) / "indexes"
        save_workbook_index(self.index, self.indexes_dir)

    def test_explains_direct_cell_reference(self):
        result = answer_query(self.indexes_dir, "demo", "explain Model!B1", orchestrator=FakeOrchestrator("explain", "Model!B1"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["intent"], "explain")
        self.assertEqual(result["target"], "Model!B1")

    def test_label_resolves_through_confirmed_table(self):
        result = answer_query(self.indexes_dir, "demo", "Revenue", orchestrator=FakeOrchestrator("value", "Revenue"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["target"], "Model!B1")

    def test_sheet_name_and_cell_without_exclamation_mark_resolves(self):
        result = answer_query(self.indexes_dir, "demo", "factors affecting Model B1", orchestrator=FakeOrchestrator("inputs", "Model B1"))
        self.assertEqual(result["target"], "Model!B1")

    def test_loads_comparison_workbook_from_persisted_index(self):
        comparison_index = deepcopy(self.index)
        comparison_index["workbook_id"] = "demo-comparison"
        comparison_index["sheets"][0]["cells"][2]["value"] = 15
        save_workbook_index(comparison_index, self.indexes_dir)

        result = answer_query(
            self.indexes_dir,
            "demo",
            "compare Revenue",
            "demo-comparison",
            orchestrator=FakeOrchestrator("compare", "Revenue"),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result"]["metric"], "Model!B1")
        self.assertEqual(result["result"]["changed_upstream_nodes"][0]["node_id"], "Model!B2")

    def test_unknown_workbook_id_raises_not_found_error(self):
        with self.assertRaisesRegex(ValueError, "Workbook not found: missing"):
            answer_query(
                self.indexes_dir,
                "missing",
                "Revenue",
                orchestrator=FakeOrchestrator("value", "Revenue"),
            )
