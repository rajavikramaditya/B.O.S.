"""B.O.S. Graph Query Filters v0.1

Filter specifications for graph query matching.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class QueryFilter:
    """Filter condition for graph query fields."""
    field: str
    operator: str  # "eq", "neq", "contains", "in", "gte", "lte"
    value: Any

    def matches(self, data: dict) -> bool:
        field_val = data.get(self.field)
        if field_val is None:
            return False

        if self.operator == "eq":
            return field_val == self.value
        elif self.operator == "neq":
            return field_val != self.value
        elif self.operator == "contains":
            return str(self.value).lower() in str(field_val).lower()
        elif self.operator == "in":
            return field_val in self.value if isinstance(self.value, (list, tuple, set)) else False
        elif self.operator == "gte":
            return field_val >= self.value
        elif self.operator == "lte":
            return field_val <= self.value
        return False
