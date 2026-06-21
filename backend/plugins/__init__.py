from __future__ import annotations
import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from .base import FlipperPlugin

logger = logging.getLogger(__name__)

_loaded: list[FlipperPlugin] = []


def load(plugin_names: list[str]) -> list[FlipperPlugin]:
    """Import and instantiate plugins by name from the plugins package."""
    plugins: list[FlipperPlugin] = []
    for name in plugin_names:
        try:
            module = importlib.import_module(f"plugins.{name}")
        except ImportError as exc:
            raise RuntimeError(f"Plugin '{name}' could not be imported: {exc}") from exc

        plugin = getattr(module, "plugin", None)
        if plugin is None or not isinstance(plugin, FlipperPlugin):
            raise RuntimeError(
                f"Plugin '{name}' must expose a top-level `plugin` instance of FlipperPlugin"
            )
        plugins.append(plugin)
        logger.info("Loaded plugin: %s v%s (required=%s)", plugin.name, plugin.version, plugin.required)

    return plugins


async def startup(app: "FastAPI", plugins: list[FlipperPlugin]) -> None:
    global _loaded
    _loaded = plugins
    for plugin in plugins:
        await plugin.on_startup(app)


async def shutdown() -> None:
    for plugin in _loaded:
        await plugin.on_shutdown()


async def db_init(db) -> None:
    """Called from database.init_db so plugins can create their own tables."""
    for plugin in _loaded:
        await plugin.on_db_init(db)


def get_all() -> list[FlipperPlugin]:
    return list(_loaded)
