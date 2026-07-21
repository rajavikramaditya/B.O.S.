"""Single source of truth for owner interpreter tools (plug-and-play registry).

Register a ToolSpec once → VALID_ACTIONS, interpreter enum, mid-loop followup
allowlist, and route membership are derived. Do not re-type frozensets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

Risk = str  # read | safe_write | confirm_required | forbidden
Route = str  # live_ops | cockpit | creative | prefs | none

Handler = Callable[["ToolContext"], dict[str, Any] | None]


@dataclass(frozen=True)
class ToolContext:
    """Shared execution context for catalog handlers."""

    action: str
    slots: dict[str, Any]
    snapshot: dict[str, Any]
    owner_message: str = ""


@dataclass
class ToolSpec:
    id: str
    description: str
    risk: Risk
    route: Route
    followup_ok: bool = False
    aliases: tuple[str, ...] = ()
    slot_hint: str = ""
    category: str = "general"
    capability_label: str | None = None
    feature_flag: str | None = None
    handler: Handler | None = field(default=None, repr=False)


_REGISTRY: dict[str, ToolSpec] = {}
_ALIAS_TO_ID: dict[str, str] = {}
_LOADED = False


def register(spec: ToolSpec) -> ToolSpec:
    """Register or replace a tool. followup_ok forced false unless risk=read."""
    if not spec.id or spec.id == "unknown":
        raise ValueError("ToolSpec.id required and must not be 'unknown'")
    followup = bool(spec.followup_ok) and spec.risk == "read"
    cleaned = ToolSpec(
        id=spec.id.strip().lower(),
        description=spec.description,
        risk=spec.risk,
        route=spec.route,
        followup_ok=followup,
        aliases=tuple(a.strip().lower() for a in (spec.aliases or ()) if a),
        slot_hint=spec.slot_hint or "",
        category=spec.category or "general",
        capability_label=spec.capability_label,
        feature_flag=spec.feature_flag,
        handler=spec.handler,
    )
    _REGISTRY[cleaned.id] = cleaned
    for alias in cleaned.aliases:
        _ALIAS_TO_ID[alias] = cleaned.id
    return cleaned


def set_handler(tool_id: str, handler: Handler) -> None:
    """Bind/replace handler on an already-registered tool."""
    spec = _REGISTRY.get((tool_id or "").strip().lower())
    if spec is None:
        raise KeyError(f"unknown tool id: {tool_id}")
    spec.handler = handler


def get(tool_id: str) -> ToolSpec | None:
    ensure_loaded()
    key = normalize_tool_id(tool_id)
    if not key or key == "unknown":
        return None
    return _REGISTRY.get(key)


def normalize_tool_id(tool_id: str) -> str:
    ensure_loaded()
    key = (tool_id or "").strip().lower()
    if not key:
        return ""
    return _ALIAS_TO_ID.get(key, key)


def all_specs() -> list[ToolSpec]:
    ensure_loaded()
    return sorted(_REGISTRY.values(), key=lambda s: s.id)


def action_ids() -> frozenset[str]:
    """Interpreter VALID_ACTIONS without the synthetic 'unknown'."""
    ensure_loaded()
    return frozenset(_REGISTRY.keys())


def valid_actions_with_unknown() -> frozenset[str]:
    return action_ids() | frozenset({"unknown"})


def followup_ids() -> frozenset[str]:
    ensure_loaded()
    return frozenset(s.id for s in _REGISTRY.values() if s.followup_ok)


def ids_for_route(route: Route) -> frozenset[str]:
    ensure_loaded()
    return frozenset(s.id for s in _REGISTRY.values() if s.route == route)


def live_ops_ids() -> frozenset[str]:
    return ids_for_route("live_ops")


def cockpit_ids() -> frozenset[str]:
    return ids_for_route("cockpit")


def creative_ids() -> frozenset[str]:
    return ids_for_route("creative")


def prefs_ids() -> frozenset[str]:
    return ids_for_route("prefs")


def build_interpreter_action_enum() -> str:
    """Pipe-separated action list for interpreter JSON schema line."""
    ids = sorted(action_ids())
    return " | ".join(ids + ["unknown"])


def build_followup_allowlist_text() -> str:
    return ", ".join(sorted(followup_ids()))


def build_interpreter_slot_hints() -> str:
    """Optional extra slot lines from specs that declare slot_hint."""
    lines: list[str] = []
    for spec in all_specs():
        if spec.slot_hint:
            lines.append(f"- {spec.id}: {spec.slot_hint}")
    return "\n".join(lines)


def execute(tool_id: str, ctx: ToolContext) -> dict[str, Any] | None:
    """Run catalog handler. Returns None if missing/unbound."""
    spec = get(tool_id)
    if spec is None or spec.handler is None:
        return None
    return spec.handler(ctx)


def ensure_loaded() -> None:
    """Import tool definitions once (registers metadata; handlers bind lazily)."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    # Import side-effect: register() calls in definitions
    from services.tools import load_all  # noqa: WPS433

    load_all()


def reset_for_tests() -> None:
    """Clear registry — tests only."""
    global _LOADED
    _REGISTRY.clear()
    _ALIAS_TO_ID.clear()
    _LOADED = False
    try:
        import services.tools as tools_pkg

        tools_pkg._LOADED = False  # type: ignore[attr-defined]
    except Exception:
        pass


__all__ = [
    "Handler",
    "Risk",
    "Route",
    "ToolContext",
    "ToolSpec",
    "action_ids",
    "all_specs",
    "build_followup_allowlist_text",
    "build_interpreter_action_enum",
    "build_interpreter_slot_hints",
    "cockpit_ids",
    "creative_ids",
    "ensure_loaded",
    "execute",
    "followup_ids",
    "get",
    "ids_for_route",
    "live_ops_ids",
    "normalize_tool_id",
    "prefs_ids",
    "register",
    "reset_for_tests",
    "set_handler",
    "valid_actions_with_unknown",
]
