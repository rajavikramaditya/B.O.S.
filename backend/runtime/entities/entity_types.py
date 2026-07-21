"""B.O.S. Entity Types v0.1

Enumeration of supported universal entity types.
"""

from enum import Enum


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    CONVERSATION = "CONVERSATION"
    WORKFLOW = "WORKFLOW"
    TASK = "TASK"
    MEETING = "MEETING"
    DOCUMENT = "DOCUMENT"
    ASSET = "ASSET"
    KNOWLEDGE = "KNOWLEDGE"
    ORDER = "ORDER"
    INVOICE = "INVOICE"
    REMINDER = "REMINDER"
    CAPABILITY = "CAPABILITY"
    EVENT = "EVENT"
