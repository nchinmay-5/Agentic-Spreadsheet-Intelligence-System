"""Required AI planning and explanation over strictly bounded workbook tools."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


INTENTS = ("value", "explain", "inputs", "impact", "compare")
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "target_text": {"type": "string"},
        "input_text": {"type": ["string", "null"]},
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "requested_tools": {"type": "array", "items": {"type": "string", "enum": ["metric_value", "direct_dependencies", "upstream_inputs", "downstream_impacts", "compare_metric"]}},
    },
    "required": ["intent", "target_text", "input_text", "needs_clarification", "clarification_question", "confidence", "requested_tools"],
}

SHEET_RANKING_SCHEMA = {"type": "object", "properties": {"sheets": {"type": "array", "items": {"type": "object", "properties": {"sheet": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["sheet", "confidence"]}}}, "required": ["sheets"]}
TABLE_PROPOSAL_SCHEMA = {"type": "object", "properties": {"ranges": {"type": "array", "items": {"type": "object", "properties": {"range": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["range", "confidence"]}}}, "required": ["ranges"]}
TABLE_CONFIRMATION_SCHEMA = {"type": "object", "properties": {"is_table": {"type": "boolean"}, "relevant_to_query": {"type": "boolean"}, "confidence": {"type": "number"}}, "required": ["is_table", "relevant_to_query", "confidence"]}
CELL_SELECTION_SCHEMA = {"type": "object", "properties": {"cell": {"type": ["string", "null"]}, "confidence": {"type": "number"}}, "required": ["cell", "confidence"]}


class AIConfigurationError(RuntimeError):
    """Raised when the required local or escalation model is unavailable."""


@dataclass
class AIOrchestrator:
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    local_model: str = os.getenv("LOCAL_MODEL", "qwen3:4b-instruct")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    escalation_threshold: float = 0.75
    request_timeout_seconds: int = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "180"))

    def plan(self, question: str, workbook_summary: dict[str, Any]) -> dict[str, Any]:
        prompt = self._planner_prompt(question, workbook_summary)
        plan = self._ollama_json(prompt, PLAN_SCHEMA)
        print(prompt)
        return self._validate_plan(plan)

    def rank_sheets(self, query: str, sheet_names: list[str]) -> list[dict[str, Any]]:
        prompt = (
            "Task: rank spreadsheet sheets for this query. Use sheet names only. "
            "Return at most 3 likely sheet names from the supplied list. Do not invent names. "
            f"Query: {query}\nSheets: {json.dumps(sheet_names)}"
        )
        result = self._ollama_json(prompt, SHEET_RANKING_SCHEMA)
        allowed = set(sheet_names)
        print(result)
        return [item for item in result.get("sheets", []) if item.get("sheet") in allowed][:3]

    def propose_table_ranges(self, query: str, sheet_context: dict[str, Any]) -> list[dict[str, Any]]:
        prompt = (
            "Task: propose up to 2 rectangular Excel ranges that may contain the answer. "
            "Use only the supplied sheet structure. A range must use A1 notation such as A1:D20. "
            "Do not explain. If unsure return an empty ranges list. "
            f"Query: {query}\nSheet structure: {json.dumps(sheet_context, default=str)}"
        )
        return self._ollama_json(prompt, TABLE_PROPOSAL_SCHEMA).get("ranges", [])[:2]

    def confirm_table(self, query: str, table: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Task: decide whether this extracted Excel range is one coherent table relevant to the query. "
            "Return false when unsure. Do not infer cells outside the range. "
            f"Query: {query}\nExtracted range: {json.dumps(table, default=str)}"
        )
        return self._ollama_json(prompt, TABLE_CONFIRMATION_SCHEMA)

    def select_table_cell(self, query: str, table: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Task: select one answer cell from the extracted table for the query. "
            "Return a cell address exactly as supplied, or null if unsure. Do not invent an address. "
            f"Query: {query}\nTable: {json.dumps(table, default=str)}"
        )
        return self._ollama_json(prompt, CELL_SELECTION_SCHEMA)
    def should_escalate(self, plan: dict[str, Any]) -> bool:
        return plan["confidence"] < self.escalation_threshold or plan["intent"] == "compare" or plan["needs_clarification"]

    def improve_plan(self, question: str, workbook_summary: dict[str, Any], local_plan: dict[str, Any]) -> dict[str, Any]:
        if not self.gemini_api_key:
            return local_plan
        prompt = self._planner_prompt(question, workbook_summary) + "\nLocal plan to review:\n" + json.dumps(local_plan)
        return self._validate_plan(self._gemini_json(prompt, PLAN_SCHEMA))

    def explain(self, question: str, plan: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
        prompt = (
            "You are a spreadsheet analyst. Write a concise business-readable answer. "
            "Use only the supplied evidence. Do not invent values, dependencies, or causation. "
            f"Question: {question}\nPlan: {json.dumps(plan)}\nEvidence: {json.dumps(evidence, default=str)}"
        )
        if self.should_escalate(plan) and self.gemini_api_key:
            response = self._gemini_json(prompt, {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]})
        else:
            response = self._ollama_json(prompt, {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]})
        return str(response["answer"])

    def _planner_prompt(self, question: str, workbook_summary: dict[str, Any]) -> str:
        return (
            "You are the required planning agent for an Excel workbook assistant. "
            "Return JSON that matches the supplied schema. Select only safe workbook tools. "
            "Ask for clarification rather than guessing an ambiguous target.\n"
            f"Workbook summary: {json.dumps(workbook_summary)}\nQuestion: {question}"
        )

    def _ollama_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            schema_prompt = prompt + "\nReturn only valid JSON matching this schema:\n" + json.dumps(schema)
            response = _post_json(
                f"{self.ollama_url.rstrip('/')}/api/chat",
                {
                    "model": self.local_model,
                    "messages": [{"role": "user", "content": schema_prompt}],
                    "stream": False,
                    "options": {"temperature": 0, "num_ctx": 4096},
                },
                timeout=self.request_timeout_seconds,
            )
            return json.loads(response["message"]["content"])
        except Exception as error:
            raise AIConfigurationError(f"Local AI agent is unavailable. Start Ollama with '{self.local_model}'.") from error

    def _gemini_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.gemini_api_key:
            raise AIConfigurationError("GEMINI_API_KEY is required for online escalation.")
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + quote(self.gemini_model, safe="") + ":generateContent?key=" + quote(self.gemini_api_key, safe="")
        response = _post_json(url, {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0, "responseMimeType": "application/json", "responseJsonSchema": schema}}, timeout=self.request_timeout_seconds)
        return json.loads(response["candidates"][0]["content"]["parts"][0]["text"])

    def _validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        if plan.get("intent") not in INTENTS:
            raise ValueError("AI planner returned an unsupported intent.")
        if not isinstance(plan.get("target_text"), str) or not 0 <= float(plan.get("confidence", -1)) <= 1:
            raise ValueError("AI planner returned an invalid plan.")
        plan["confidence"] = float(plan["confidence"])
        plan["requested_tools"] = [tool for tool in plan.get("requested_tools", []) if tool in PLAN_SCHEMA["properties"]["requested_tools"]["items"]["enum"]]
        print(plan)
        return plan


def _post_json(url: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:  # nosec - endpoint configured by the user
        return json.loads(response.read().decode("utf-8"))
