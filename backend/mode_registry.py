"""
Central registry for all display modes — built-in and plugin-provided.

Each mode registers a ModeDefinition with metadata and an async render
function. The render function receives (rows, cols, config, settings) and
returns a matrix (list[list[int]]).

Built-in modes are registered during app startup. Plugin modes are registered
when the plugin's on_startup() hook runs.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Awaitable

Matrix = list[list[int]]
RenderFn = Callable[[int, int, dict, dict], Awaitable[Matrix]]


@dataclass
class ModeDefinition:
    id: str
    label: str
    icon: str = "⬡"
    description: str = ""
    config_schema: dict = field(default_factory=dict)
    render: RenderFn | None = None


_registry: dict[str, ModeDefinition] = {}


def register(mode: ModeDefinition) -> None:
    _registry[mode.id] = mode


def get(mode_id: str) -> ModeDefinition | None:
    return _registry.get(mode_id)


def all_modes() -> list[dict]:
    """Serializable catalog — used by the /api/modes/available endpoint."""
    return [
        {
            "id": m.id,
            "label": m.label,
            "icon": m.icon,
            "description": m.description,
            "config_schema": m.config_schema,
        }
        for m in _registry.values()
    ]


async def render(
    mode_id: str, rows: int, cols: int, config: dict, settings: dict
) -> Matrix | None:
    """Dispatch to the registered render function; returns None if not found."""
    mode = _registry.get(mode_id)
    if mode and mode.render:
        return await mode.render(rows, cols, config, settings)
    return None
