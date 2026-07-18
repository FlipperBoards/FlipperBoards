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
    """Import and instantiate plugins by name from the plugins package.

    Sets _loaded immediately so on_db_init hooks work during database.init_db().
    """
    global _loaded
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

    _loaded = plugins
    return plugins


async def startup(app: FastAPI, plugins: list[FlipperPlugin]) -> None:
    """Register each plugin's modes then call on_startup."""
    import mode_registry
    for plugin in plugins:
        for mode in plugin.modes:
            mode_registry.register(mode)
            logger.info("Registered mode '%s' from plugin '%s'", mode.id, plugin.name)
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
