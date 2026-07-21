"""B.O.S. Capability Reasoner v0.1

Reasoning over platform capability selection and capability graph dependencies.
"""

from typing import List
from ..intent import IntentObject


class CapabilityReasoner:
    """Selects and sequences required capabilities based on intent."""

    @classmethod
    def reason(cls, intent: IntentObject) -> List[str]:
        caps = intent.required_capabilities or ["messaging"]
        return caps
