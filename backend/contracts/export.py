"""실행: uv run python -m contracts.export."""

import json
from pathlib import Path

from contracts.analysis import AnalysisEvent, AnalysisRequest, Report, Transcript, UtterancesWrite
from contracts.models import (
    ErrorResponse,
    ProjectCreate,
    ProjectPatch,
    UploadComplete,
    UploadCreate,
)

SCHEMAS = {
    "project_create": ProjectCreate,
    "project_patch": ProjectPatch,
    "upload_create": UploadCreate,
    "upload_complete": UploadComplete,
    "analysis_request": AnalysisRequest,
    "analysis_event": AnalysisEvent,
    "utterances_write": UtterancesWrite,
    "transcript": Transcript,
    "report": Report,
    "error": ErrorResponse,
}

if __name__ == "__main__":
    target = Path(__file__).parent / "schemas"
    target.mkdir(exist_ok=True)
    for name, model in SCHEMAS.items():
        (target / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
