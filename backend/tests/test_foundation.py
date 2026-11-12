import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from analysis.api.main import app as analysis_app
from api.main import app
from contracts.analysis import Report
from contracts.export import SCHEMAS
from contracts.models import JobStatus, Page, ProjectPatch, Role

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def example(name: str) -> dict:
    return json.loads((CONTRACTS / "examples" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("service", [app, analysis_app])
def test_health_and_openapi(service):
    with TestClient(service) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert "/healthz" in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("name,model", SCHEMAS.items())
def test_examples_and_exported_schema(name, model):
    model.model_validate_json((CONTRACTS / "examples" / f"{name}.json").read_text(encoding="utf-8"))
    assert (
        json.loads((CONTRACTS / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        == model.model_json_schema()
    )


@pytest.mark.parametrize("score", [-1, 101, 70.5, "80", True, float("inf")])
def test_scores_are_integers_in_range(score):
    with pytest.raises(ValidationError):
        Report.model_validate({**example("report"), "totalScore": score})


def test_patch_omission_and_explicit_null_are_different():
    patch = ProjectPatch.model_validate({"finalDate": None})
    assert patch.model_dump(exclude_unset=True, by_alias=False) == {"final_date": None}
    assert patch.model_dump(exclude_unset=True) == {"finalDate": None}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"done": None},
        {"done": 1},
        {"targetMinutes": None},
        {"target_minutes": 10},
    ],
)
def test_invalid_patch(payload):
    with pytest.raises(ValidationError):
        ProjectPatch.model_validate(payload)


def test_page_defaults_and_size_limit():
    assert Page(total=0).model_dump() == {"number": 0, "size": 20, "total": 0}
    with pytest.raises(ValidationError):
        Page(size=101, total=0)


def test_v9_roles_and_full_analysis_stages():
    assert {role.value for role in Role} == {"USER", "ADMIN"}
    assert {status.value for status in JobStatus} == {
        "QUEUED",
        "EXTRACTING",
        "ANALYZING",
        "SCORING",
        "DONE",
        "FAILED",
    }


def test_cors_allows_only_configured_origin():
    with TestClient(app) as client:
        allowed = client.options(
            "/healthz",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT"},
        )
        denied = client.options(
            "/healthz",
            headers={"Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "GET"},
        )
        response = client.get("/healthz", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers
    assert "X-Request-Id" in response.headers["access-control-expose-headers"]
    assert "Retry-After" in response.headers["access-control-expose-headers"]


def test_schemas_do_not_advertise_invalid_null_defaults():
    schema = ProjectPatch.model_json_schema()
    assert schema["minProperties"] == 1
    assert "default" not in schema["properties"]["targetMinutes"]
    assert schema["properties"]["finalDate"]["default"] is None


@pytest.mark.parametrize("value", [0, "20261109", "2026-02-30", "2026-11-09T00:00:00Z"])
def test_calendar_date_format(value):
    with pytest.raises(ValidationError):
        ProjectPatch.model_validate({"finalDate": value})


def test_only_current_schema_files_are_exported():
    assert {
        path.stem.removesuffix(".schema") for path in (CONTRACTS / "schemas").glob("*.json")
    } == (set(SCHEMAS))


def test_endpoint_catalog_contains_individual_routes():
    catalog = json.loads((CONTRACTS / "endpoint-catalog.json").read_text(encoding="utf-8"))
    endpoints = catalog["endpoints"]
    identities = {(e["service"], e["method"], e["path"]) for e in endpoints}
    assert len(identities) == len(endpoints)
    for endpoint in endpoints:
        assert "," not in endpoint["path"]
        assert " " not in endpoint["path"]
        assert not endpoint["path"].startswith("/expert/")
