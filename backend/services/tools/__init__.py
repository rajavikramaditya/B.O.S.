"""Owner tool plugins — catalog, definitions, loop, Gemini legacy registry.

To add a tool:
1. Create services/tools/<category>/<name>.py with handler + register(ToolSpec(...))
2. Import that module inside load_all()
3. Done — interpreter / followup / routing derive from services.tools.catalog

Do not put new owner CC tools in legacy_gemini_registry.py.
"""
from __future__ import annotations

_LOADED = False


def load_all() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    from services.tools.definitions import register_builtin_definitions

    register_builtin_definitions()
    from services.tools.catalog_health import register_catalog_health

    register_catalog_health()
    from services.tools.self_change_status import register_self_change_status

    register_self_change_status()
    from services.tools.deferred_whatsapp_status import register_arm_deferred_status

    register_arm_deferred_status()
    from services.tools.memory_notebook import register_memory_notebook_tools

    register_memory_notebook_tools()
    from services.tools.customer_whatsapp import register_customer_whatsapp_tools

    register_customer_whatsapp_tools()
    from services.tools.station_plan import register_station_plan_tools

    register_station_plan_tools()
    from services.tools import bind_handlers

    bind_handlers.bind_all()


__all__ = ["load_all"]
