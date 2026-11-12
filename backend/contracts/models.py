"""공통 HTTP 계약과 ERD v9의 점수 구성요소. 전체 업무 API 구현은 별도다."""

import re
from datetime import date
from enum import Enum
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, model_validator
from pydantic.alias_generators import to_camel

NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
Score = Annotated[int, Field(strict=True, ge=0, le=100)]
T = TypeVar("T")


def calendar_date(value):
    if value is not None and not isinstance(value, date):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다")
    return value


CalendarDate = Annotated[date, BeforeValidator(calendar_date)]


def omit_nonnullable_null_defaults(schema: dict) -> None:
    # 생략 표시용 None을 JSON Schema의 유효한 기본값으로 노출하지 않는다.
    for field in schema.get("properties", {}).values():
        if field.get("type") not in (None, "null") and field.get("default", False) is None:
            field.pop("default")


class Contract(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        json_schema_extra=omit_nonnullable_null_defaults,
        serialize_by_alias=True,
        extra="forbid",
        allow_inf_nan=False,
    )


class Role(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    ANALYZING = "ANALYZING"
    SCORING = "SCORING"
    DONE = "DONE"
    FAILED = "FAILED"


class QaStatus(str, Enum):
    READY = "READY"
    LIVE = "LIVE"
    WRAP_UP = "WRAP_UP"
    ENDED = "ENDED"


class MaterialStatus(str, Enum):
    NONE = "NONE"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED = "FAILED"


class DataResponse(Contract, Generic[T]):
    data: T


class Page(Contract):
    number: NonNegativeInt = 0
    size: Annotated[int, Field(strict=True, ge=1, le=100)] = 20
    total: NonNegativeInt


class PageResponse(Contract, Generic[T]):
    data: list[T]
    page: Page


class ApiError(Contract):
    code: str
    message: str
    fields: dict[str, str] = Field(default_factory=dict)
    details: dict = Field(default_factory=dict)
    retryable: StrictBool = False
    request_id: str


class ErrorResponse(Contract):
    error: ApiError


class ProjectCreate(Contract):
    name: str
    topic: str
    final_date: CalendarDate | None = None
    target_minutes: NonNegativeInt = 30


def project_patch_schema(schema: dict) -> None:
    omit_nonnullable_null_defaults(schema)
    schema["minProperties"] = 1


class ProjectPatch(Contract):
    model_config = ConfigDict(json_schema_extra=project_patch_schema)

    # 생략은 유지, 명시적 null은 finalDate에만 허용한다.
    name: str = None
    topic: str = None
    final_date: CalendarDate | None = None
    target_minutes: NonNegativeInt = None
    done: StrictBool = None

    @model_validator(mode="after")
    def require_change(self) -> "ProjectPatch":
        if not self.model_fields_set:
            raise ValueError("최소 한 필드가 필요합니다")
        return self


class UploadCreate(Contract):
    file_name: str
    size_bytes: Annotated[int, Field(strict=True, ge=1, le=524_288_000)]
    content_type: Literal["video/mp4", "video/quicktime"]
    checksum: Annotated[str, Field(pattern=r"^[a-fA-F0-9]{64}$")]


class UploadComplete(Contract):
    pass
