"""사용자 API의 공통 오류 계약. 입력값·예외 원문은 응답에 포함하지 않는다."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from contracts.models import ErrorResponse

DEFAULT_CODES = {
    400: "VALIDATION_FAILED",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "INVALID_STATE",
    410: "ALREADY_DELETED",
    413: "UPLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "TEMPORARILY_UNAVAILABLE",
}


class ApiException(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        fields: dict[str, str] | None = None,
        details: dict | None = None,
        retryable: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, headers=headers)
        self.payload = {
            "code": code,
            "message": message,
            "fields": fields or {},
            "details": details or {},
            "retryable": retryable,
        }


def error_response(request: Request, status: int, payload: dict, headers=None) -> JSONResponse:
    request_id = request.state.request_id
    body = ErrorResponse.model_validate({"error": {**payload, "requestId": request_id}})
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers={**(headers or {}), "X-Request-Id": request_id},
    )


def configure_errors(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception as exc:
            logging.getLogger(__name__).error(
                "requestId=%s errorType=%s", request.state.request_id, type(exc).__name__
            )
            response = error_response(
                request,
                500,
                {
                    "code": "INTERNAL_ERROR",
                    "message": "서버 오류가 발생했습니다.",
                },
            )
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        fields = {
            ".".join(str(part) for part in error["loc"]): "필드 형식과 필수 여부를 확인하세요."
            for error in exc.errors()
        }
        return error_response(
            request,
            422 if request.url.path.startswith("/internal/") else 400,
            {
                "code": "VALIDATION_FAILED",
                "message": "요청 형식을 확인하세요.",
                "fields": fields,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        payload = (
            exc.payload
            if isinstance(exc, ApiException)
            else {
                "code": DEFAULT_CODES.get(exc.status_code, "HTTP_ERROR"),
                "message": "요청을 처리할 수 없습니다.",
                "retryable": exc.status_code in (429, 503),
            }
        )
        return error_response(request, exc.status_code, payload, exc.headers)

    original_openapi = app.openapi

    def contract_openapi():
        schema = original_openapi()
        # Pydantic의 로컬 $defs 참조를 OpenAPI components 참조로 생성한다.
        error_schema = ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
        definitions = error_schema.pop("$defs", {})
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        components.update(definitions)
        components["ErrorResponse"] = error_schema
        for path_name, path in schema.get("paths", {}).items():
            validation_status = "422" if path_name.startswith("/internal/") else "400"
            for operation in path.values():
                if not isinstance(operation, dict):
                    continue
                responses = operation.get("responses", {})
                if "422" in responses:
                    responses.pop("422")
                    responses.setdefault(
                        validation_status,
                        {
                            "description": "VALIDATION_FAILED",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                                }
                            },
                        },
                    )
        return schema

    app.openapi = contract_openapi
