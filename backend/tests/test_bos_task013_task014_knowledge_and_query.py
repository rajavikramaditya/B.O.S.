"""Tests for TASK-013 Knowledge Graph & TASK-014 Graph Query Engine."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.business_graph import BusinessContextGraph, BusinessNode, RelationshipType
from runtime.knowledge_graph import KnowledgeGraph, KnowledgeNode, KnowledgeQueryEngine
from runtime.graph_query import GraphQueryEngine, GraphQuery, QueryFilter


def test_knowledge_graph_and_query():
    kg = KnowledgeGraph()
    kn1 = KnowledgeNode(category="Policy", title="Refund Policy", content="Refunds allowed within 30 days.", tags=["refund", "sales"])
    kn2 = KnowledgeNode(category="FAQ", title="Shipping FAQ", content="Shipping takes 3-5 days.", tags=["shipping"])

    kg.add_node(kn1)
    kg.add_node(kn2)

    res = KnowledgeQueryEngine.query_knowledge(kg, "refund")
    assert len(res) == 1
    assert res[0]["title"] == "Refund Policy"


def test_graph_query_engine_unified():
    bg = BusinessContextGraph()
    b_node = BusinessNode(node_type="Customer", name="Ramesh", attributes={"city": "Orai"})
    bg.add_node(b_node)

    res = GraphQueryEngine.find_entity("Customer", bg, filters={"city": "Orai"})
    assert len(res) == 1
    assert res[0]["name"] == "Ramesh"
