from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import Settings
from api.core.errors import configure_errors
from api.routers.health import router

settings = Settings()
app = FastAPI(title="ProPitch API", version="0.1.0")
configure_errors(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    expose_headers=["X-Request-Id", "Retry-After"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(router)
