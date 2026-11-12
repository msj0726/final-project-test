from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    # 프로세스 생존 확인이며 DB·큐 연결 상태를 의미하지 않는다.
    return HealthResponse()
