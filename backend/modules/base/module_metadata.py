"""B.O.S. Module Metadata v0.1

Metadata dataclass describing module properties.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ModuleMetadata:
    """Metadata describing an installable B.O.S. Business Module."""
    name: str
    version: str = "1.0.0"
    author: str = "B.O.S. Core Team"
    description: str = ""
    category: str = "general"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "category": self.category,
        }
