# WHY: TR-TEST-01 — Pytest fixtures for Ale Voice
"""Test configuration and async fixtures."""

import os
import sys

# Ensure repository root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from httpx import AsyncClient, ASGITransport
from apps.api.main import app
from apps.api.core.database import init_db


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Initialise database before running test suite."""
    await init_db()
    yield


@pytest.fixture
async def client():
    """Async test client for FastAPI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
