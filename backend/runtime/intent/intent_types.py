"""B.O.S. Intent Types & Categories v0.1

Enumeration of intent categories, priorities, and urgency levels.
"""

from enum import Enum


class IntentCategory(str, Enum):
    COMMAND = "COMMAND"
    INQUIRY = "INQUIRY"
    WORKFLOW_REQUEST = "WORKFLOW_REQUEST"
    APPROVAL_REPLY = "APPROVAL_REPLY"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    UNKNOWN = "UNKNOWN"


class PriorityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UrgencyLevel(str, Enum):
    NORMAL = "NORMAL"
    DEFERRED = "DEFERRED"
    IMMEDIATE = "IMMEDIATE"
