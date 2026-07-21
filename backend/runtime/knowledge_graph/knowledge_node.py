"""B.O.S. Knowledge Graph Node v0.1

Node representing facts, policies, documents, FAQs, manuals, rules, or references.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class KnowledgeNode:
    """Node storing domain knowledge (e.g., Policy, FAQ, Rule)."""
    category: str  # "Fact", "Policy", "Document", "FAQ", "Manual", "Rule", "Reference"
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    node_id: str = field(default_factory=lambda: f"know_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "metadata": self.metadata,
        }
