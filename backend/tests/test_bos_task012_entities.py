"""Tests for TASK-012: Universal Entity Model."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.entities import UniversalEntity, EntityType


def test_universal_entity_creation():
    ent = UniversalEntity(
        entity_type=EntityType.ORGANIZATION,
        name="TechCorp",
        owner="admin",
        tags=["tech", "vendor"],
    )
    assert ent.entity_id.startswith("ent_")
    assert ent.name == "TechCorp"
    assert ent.status == "ACTIVE"

    ent.add_relationship("ent_person_1", "EMPLOYEE")
    assert len(ent.relationships) == 1
    assert ent.relationships[0]["target_id"] == "ent_person_1"

    d = ent.to_dict()
    assert d["entity_type"] == "ORGANIZATION"
    assert d["tags"] == ["tech", "vendor"]
