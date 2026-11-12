from fastapi import FastAPI

from api.routers.health import router

app = FastAPI(title="발표 코칭 Analysis (내부 전용)", version="0.1.0")
app.include_router(router)
