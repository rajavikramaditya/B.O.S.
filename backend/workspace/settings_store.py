"""B.O.S. Workspace Settings Store v1.0

Key/value settings: business profile, autopilot preferences, onboarding state.
"""

import copy
from typing import Any, Dict

from .database import WorkspaceDatabase
from .models import Setting

BUSINESS_PROFILE = "business_profile"
AUTOPILOT = "autopilot"

DEFAULTS: Dict[str, Any] = {
    BUSINESS_PROFILE: {
        "name": "",
        "industry": "",
        "description": "",
        "offerings": "",
        "target_customers": "",
        "goals": [],
        "tone": "warm, professional",
        "languages": ["English", "Hinglish"],
        "assistant_name": "Neena",
        "website": "",
        "hours": "",
        "location": "",
    },
    AUTOPILOT: {
        "mode": "autopilot",
        "briefing_enabled": True,
    },
}

AUTOPILOT_MODES = ("off", "assist", "autopilot", "autonomous")


class SettingsStore:
    """Typed access to workspace settings with defaults merged in."""

    @staticmethod
    def get(key: str) -> Dict[str, Any]:
        base = copy.deepcopy(DEFAULTS.get(key, {}))
        with WorkspaceDatabase.session() as db:
            row = db.get(Setting, key)
            if row and isinstance(row.value, dict):
                base.update(row.value)
        return base

    @staticmethod
    def update(key: str, values: Dict[str, Any]) -> Dict[str, Any]:
        merged = SettingsStore.get(key)
        merged.update({k: v for k, v in values.items() if v is not None})
        with WorkspaceDatabase.session() as db:
            row = db.get(Setting, key)
            if row:
                row.value = merged
            else:
                db.add(Setting(key=key, value=merged))
        return merged

    @staticmethod
    def raw(key: str, default: Any = None) -> Any:
        with WorkspaceDatabase.session() as db:
            row = db.get(Setting, key)
            return row.value if row else default

    @staticmethod
    def set_raw(key: str, value: Any) -> None:
        with WorkspaceDatabase.session() as db:
            row = db.get(Setting, key)
            if row:
                row.value = value
            else:
                db.add(Setting(key=key, value=value))

    @staticmethod
    def autopilot_mode() -> str:
        mode = SettingsStore.get(AUTOPILOT).get("mode", "autopilot")
        return mode if mode in AUTOPILOT_MODES else "autopilot"
