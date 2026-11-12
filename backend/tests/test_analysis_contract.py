import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.analysis import AnalysisEvent, AnalysisRequest, Report, UtterancesWrite
from contracts.models import UploadCreate


def example(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "contracts" / "examples" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("field", ["videoKey", "materialKeys", "projectTopic", "roundId"])
def test_removed_fields_rejected(field):
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate({**example("analysis_request"), field: "not-allowed"})


@pytest.mark.parametrize("patch", [{"jobId": "an_01"}, {"attempt": 0}, {"attempt": True}])
def test_job_ids_and_attempt(patch):
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate({**example("analysis_request"), **patch})


@pytest.mark.parametrize("patch", [{"seq": 2}, {"startSec": 1}, {"endSec": -1}])
def test_utterance_sequence_and_interval(patch):
    data = example("utterances_write")
    data["utterances"][0].update(patch)
    with pytest.raises(ValidationError):
        UtterancesWrite.model_validate(data)


def test_duration_and_report_context():
    transcript = UtterancesWrite.model_validate(example("utterances_write"))
    with pytest.raises(ValueError):
        transcript.validate_duration(0.5)
    report = Report.model_validate(example("report"))
    job = AnalysisRequest.model_validate(example("analysis_request"))
    items = {s.rubric_item_id: (s.item_key, s.weight) for s in report.scores}
    report.validate_context(job, 1, items)
    with pytest.raises(ValueError):
        report.validate_context(job, 0.5, items)
    with pytest.raises(ValueError):
        report.validate_context(job, 1, {})


@pytest.mark.parametrize(
    "patch", [{"contentCheck": {}}, {"totalScore": 80.5}, {"quality": {"level": "NORMAL"}}]
)
def test_report_rules(patch):
    with pytest.raises(ValidationError):
        Report.model_validate({**example("report"), **patch})


@pytest.mark.parametrize(
    "patch", [{"progress": 99}, {"stage": "FEEDBACK"}, {"occurredAt": "2026-11-10T09:00:00+09:00"}]
)
def test_event_state_rules(patch):
    with pytest.raises(ValidationError):
        AnalysisEvent.model_validate({**example("analysis_event"), **patch})


@pytest.mark.parametrize(
    "patch",
    [
        {"sizeBytes": 524288001},
        {"checksum": "not-sha256"},
        {"contentType": "video/webm"},
        {"durationSec": 1},
    ],
)
def test_upload_limits(patch):
    with pytest.raises(ValidationError):
        UploadCreate.model_validate({**example("upload_create"), **patch})


def test_v10_equal_weights():
    data = example("report")
    data["scores"][0]["weight"] = 1.0
    with pytest.raises(ValidationError):
        Report.model_validate(data)
