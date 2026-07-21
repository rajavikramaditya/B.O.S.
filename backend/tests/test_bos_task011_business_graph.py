"""Tests for TASK-011: Business Context Graph."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.business_graph import (
    BusinessContextGraph,
    BusinessNode,
    RelationshipType,
)


def test_business_context_graph_topology():
    graph = BusinessContextGraph()

    b_node = BusinessNode(node_type="Business", name="Acme Corp")
    d_node = BusinessNode(node_type="Department", name="Sales")
    e_node = BusinessNode(node_type="Employee", name="Alice")
    c_node = BusinessNode(node_type="Customer", name="Bob")

    b_id = graph.add_node(b_node)
    d_id = graph.add_node(d_node)
    e_id = graph.add_node(e_node)
    c_id = graph.add_node(c_node)

    graph.add_edge(b_id, d_id, RelationshipType.CONTAINS)
    graph.add_edge(d_id, e_id, RelationshipType.EMPLOYED_BY)
    graph.add_edge(e_id, c_id, RelationshipType.SERVES)

    # Resolve customer starting from Business
    customers = graph.find_related_entities(b_id, "Customer")
    assert len(customers) == 1
    assert customers[0].name == "Bob"
