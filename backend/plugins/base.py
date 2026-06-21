from __future__ import annotations
from abc import ABC


class FlipperPlugin(ABC):
    """Base class for all FlipperBoards plugins.

    Self-hosted ships with no plugins. The SaaS version loads plugins like
    billing as required. Each plugin can register routes, add DB tables, and
    hook into startup/shutdown.
    """
    name: str = ""
    version: str = "0.1.0"
    required: bool = False

    async def on_startup(self, app) -> None:
        """Called after the app and DB are initialized. Register routes here."""

    async def on_shutdown(self) -> None:
        """Called on app shutdown."""

    async def on_db_init(self, db) -> None:
        """Called inside init_db — create plugin-specific tables here."""
