from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mode_registry import ModeDefinition


class FlipperPlugin(ABC):
    """Base class for all FlipperBoards plugins.

    Self-hosted ships with no plugins. The SaaS version loads plugins like
    billing as required. Contributor plugins add new display modes (Spotify,
    YouTube stats, stock tickers, etc.).

    Lifecycle:
      1. on_db_init(db)  — create plugin-specific tables
      2. modes           — register display modes with the mode registry
      3. on_startup(app) — register FastAPI routes, middleware, etc.
      4. on_shutdown()   — cleanup

    Example plugin (plugins/spotify/__init__.py):

        from plugins.base import FlipperPlugin
        from mode_registry import ModeDefinition

        class SpotifyPlugin(FlipperPlugin):
            name = "spotify"
            version = "0.1.0"

            @property
            def modes(self):
                return [
                    ModeDefinition(
                        id="spotify",
                        label="Spotify",
                        icon="🎵",
                        description="Now playing on Spotify",
                        config_schema={"client_id": {}, "client_secret": {}},
                        render=self._render,
                    )
                ]

            async def _render(self, rows, cols, config, settings):
                # fetch from Spotify API, return matrix
                ...

        plugin = SpotifyPlugin()
    """
    name: str = ""
    version: str = "0.1.0"
    required: bool = False

    @property
    def modes(self) -> list["ModeDefinition"]:
        """Display modes this plugin provides. Override to add modes."""
        return []

    async def on_startup(self, app) -> None:
        """Called after DB init and mode registration. Register routes here."""

    async def on_shutdown(self) -> None:
        """Called on app shutdown."""

    async def on_db_init(self, db) -> None:
        """Called inside init_db — create plugin-specific tables here."""
