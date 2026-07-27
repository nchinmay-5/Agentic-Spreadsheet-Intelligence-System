"""FastAPI boundary for upload, processing, and evidence-grounded queries."""

from __future__ import annotations

import shutil
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.agents.workflow import build_query_workflow
from app.agents.ai_orchestrator import AIConfigurationError
from app.ingestion.workbook_indexer import index_workbook_to_file

app = FastAPI(title="Spreadsheet Intelligence API")
upload_dir = Path("data/uploads")
indexes_dir = Path("data/indexes")
query_workflow = build_query_workflow(indexes_dir)


class QueryRequest(BaseModel):
    workbook_id: str
    question: str
    comparison_workbook_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/workbooks")
async def upload_workbook(file: UploadFile = File(...)) -> dict:
    if not file.filename or Path(file.filename).suffix.lower() != ".xlsx":
        raise HTTPException(400, "Upload an .xlsx workbook.")
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / Path(file.filename).name
    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    index, index_path = index_workbook_to_file(destination, indexes_dir)

    return {"workbook_id": index["workbook_id"], "index_path": str(index_path), "sheets": index["sheet_names"]}


@app.post("/query")
def query(request: QueryRequest) -> dict:
    try:
        state = query_workflow.invoke(request.model_dump())
        return state["response"]
    except AIConfigurationError as error:
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
