"""Shared fixtures.

FB_DB_PATH must point at a throwaway file BEFORE any app module is imported,
because config.Settings and database.DB_PATH bind at import time.
"""
import os
import sys
import tempfile

import pytest_asyncio

_TMPDIR = tempfile.mkdtemp(prefix="fb-test-")
os.environ["FB_DB_PATH"] = os.path.join(_TMPDIR, "test.db")
os.environ["FB_UPLOAD_DIR"] = os.path.join(_TMPDIR, "uploads")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from asgi_lifespan import LifespanManager

import main  # noqa: E402  (after env setup, deliberately)


@pytest_asyncio.fixture()
async def client():
    """App with lifespan running (rotation/clock tasks live) + HTTP client."""
    async with LifespanManager(main.app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://test") as c:
            yield c


@pytest_asyncio.fixture()
async def clean_playlist(client):
    """Ensure the main screen's playlist is empty before and after a test."""
    await client.post("/api/playlist/clear?screen=main")
    yield client
    await client.post("/api/playlist/clear?screen=main")
