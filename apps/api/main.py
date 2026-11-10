# WHY: D1 — Stack decision: Python 3.12 + FastAPI + SQLAlchemy 2 + PostgreSQL (SQLite fallback)
"""Ale Voice — FastAPI Backend Application."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apps.api.core.config import settings
from apps.api.core.database import init_db
from apps.api.core.seed import seed_database
from apps.api.routers.voice import router as voice_router
from apps.api.routers.auth import router as auth_router
from apps.api.routers.weather import router as weather_router
from apps.api.routers.trips import router as trips_router
from apps.api.routers.market import router as market_router
from apps.api.routers.diary import router as diary_router
from apps.api.routers.family import router as family_router
from apps.api.routers.guard import router as guard_router
from apps.api.routers.sync import router as sync_router
from apps.api.routers.devices import devices_router, app_router
from apps.api.routers.admin import admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB and seed core data on startup."""
    await init_db()
    await seed_database()
    yield


app = FastAPI(
    title="Ale Voice API",
    version="0.1.0",
    description="Voice-first companion for coastal fishers — Gnani AI Challenge",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "mock_providers": settings.mock_providers,
        "db_type": "sqlite" if settings.use_sqlite else "postgresql",
    }


app.include_router(voice_router)
app.include_router(auth_router)
app.include_router(weather_router)
app.include_router(trips_router)
app.include_router(market_router)
app.include_router(diary_router)
app.include_router(family_router)
app.include_router(guard_router)
app.include_router(sync_router)
app.include_router(devices_router)
app.include_router(app_router)
app.include_router(admin_router)

# Mount audio cache for synthesized speech playback
os.makedirs("audio_cache", exist_ok=True)
app.mount("/api/v1/audio", StaticFiles(directory="audio_cache"), name="audio_cache")

# Mount Admin Console (must be mounted before root static)
admin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "admin")
if os.path.exists(admin_dir):
    app.mount("/admin", StaticFiles(directory=admin_dir, html=True), name="admin")

# Mount frontend PWA shell (must be mounted last)
web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="static")

