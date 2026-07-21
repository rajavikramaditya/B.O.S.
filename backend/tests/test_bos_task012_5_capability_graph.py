"""Tests for TASK-012.5: Capability Graph."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from core.graph.capability import (
    CapabilityGraph,
    CapabilityNode,
    CapabilityResolver,
)


def test_capability_graph_topology_and_discovery():
    graph = CapabilityGraph()

    # Discover what 'messaging' enhances
    enhancements = CapabilityResolver.find_related_capabilities(graph, "messaging", "ENHANCES")
    assert len(enhancements) == 1
    assert enhancements[0].name == "notification"

    # Discover prerequisites for 'workflow'
    prereqs = CapabilityResolver.find_prerequisites(graph, "workflow")
    prereq_names = [p.name for p in prereqs]
    assert "approval" in prereq_names or "automation" in prereq_names
