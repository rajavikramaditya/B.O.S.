"""B.O.S. Workspace Package v1.0

Business database for one deployment: profile, records, approvals, integrations.
Kept strictly separate from conversation memory.
"""

from .database import WorkspaceDatabase
from .vault import WorkspaceVault
from .settings_store import SettingsStore
from .activity import ActivityLog

__all__ = ["WorkspaceDatabase", "WorkspaceVault", "SettingsStore", "ActivityLog"]
