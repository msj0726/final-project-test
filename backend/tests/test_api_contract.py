import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient

from api.core.errors import ApiException, configure_errors
from contracts.models import DataResponse, ErrorResponse, ProjectCreate, UploadCreate


@pytest.fixture
def client():
    app = FastAPI()
    configure_errors(app)

    @app.post("/projects", response_model=DataResponse[ProjectCreate], status_code=201)
    def create_project(project: ProjectCreate):
        return {"data": project}

    @app.post("/uploads", status_code=204)
    def create_upload(upload: UploadCreate):
        return Response(status_code=204)

    @app.get("/conflict")
    def conflict():
        raise ApiException(
            409, "OPERATION_IN_PROGRESS", "처리 중입니다.", headers={"Retry-After": "3"}
        )

    @app.get("/unauthenticated")
    def unauthenticated():
        raise HTTPException(
            401, detail="secret-internal-detail", headers={"WWW-Authenticate": "Bearer"}
        )

    @app.get("/crash")
    def crash():
        raise RuntimeError("secret-token")

    @app.delete("/resource", status_code=204)
    def delete():
        return Response(status_code=204)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_camel_case_and_success_envelope(client):
    response = client.post("/projects", json={"name": "발표", "topic": "AI"})
    assert response.status_code == 201
    assert response.json() == {
        "data": {
            "name": "발표",
            "topic": "AI",
            "finalDate": None,
            "targetMinutes": 30,
        }
    }
    assert "x-request-id" in response.headers


@pytest.mark.parametrize(
    "extra",
    [
        {"targetMinutes": None},
        {"targetMinutes": -1},
        {"targetMinutes": True},
        {"target_minutes": 5},
        {"unknown": "secret-token"},
    ],
)
def test_validation_is_safe_400(client, extra):
    response = client.post("/projects", json={"name": "발표", "topic": "AI", **extra})
    assert response.status_code == 400
    error = ErrorResponse.model_validate(response.json()).error
    assert error.code == "VALIDATION_FAILED"
    assert error.request_id == response.headers["x-request-id"]
    assert error.fields
    assert "secret-token" not in response.text
    assert "detail" not in response.json()


def test_bad_json_is_safe_400(client):
    response = client.post(
        "/projects",
        content='{"password":"secret-token",',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "secret-token" not in response.text


def test_removed_upload_fields_are_rejected(client):
    data = {
        "fileName": "example.mp4",
        "sizeBytes": 1,
        "contentType": "video/mp4",
        "checksum": "a" * 64,
    }
    assert client.post("/uploads", json=data).status_code == 204
    assert client.post("/uploads", json={**data, "durationSec": None}).status_code == 400


@pytest.mark.parametrize(
    "path,status,code",
    [
        ("/missing", 404, "NOT_FOUND"),
        ("/conflict", 409, "OPERATION_IN_PROGRESS"),
        ("/unauthenticated", 401, "UNAUTHENTICATED"),
        ("/crash", 500, "INTERNAL_ERROR"),
    ],
)
def test_errors_share_contract(client, path, status, code):
    response = client.get(path)
    assert response.status_code == status
    error = ErrorResponse.model_validate(response.json()).error
    assert error.code == code
    assert error.request_id == response.headers["x-request-id"]
    assert "secret" not in response.text
    if status == 409:
        assert response.headers["retry-after"] == "3"
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"


def test_204_is_empty(client):
    response = client.delete("/resource")
    assert response.status_code == 204
    assert response.content == b""


def test_openapi_documents_actual_validation_response(client):
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/projects"]["post"]["responses"]
    assert "422" not in responses
    assert responses["400"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse",
    }
    assert "ApiError" in schema["components"]["schemas"]
