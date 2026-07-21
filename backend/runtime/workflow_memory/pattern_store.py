"""B.O.S. Workflow Pattern Store v0.1

Indexes and stores reusable successful workflow graph patterns.
"""

from typing import Any, Dict, List, Optional


class PatternStore:
    """Stores successful workflow graph execution patterns for future reuse."""

    _patterns: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def save_pattern(cls, pattern_id: str, pattern_data: Dict[str, Any]) -> None:
        cls._patterns[pattern_id] = pattern_data

    @classmethod
    def get_pattern(cls, pattern_id: str) -> Optional[Dict[str, Any]]:
        return cls._patterns.get(pattern_id)

    @classmethod
    def list_patterns(cls) -> List[Dict[str, Any]]:
        return list(cls._patterns.values())

    @classmethod
    def clear(cls) -> None:
        cls._patterns.clear()
