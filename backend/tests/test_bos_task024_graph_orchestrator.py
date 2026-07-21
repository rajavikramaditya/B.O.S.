"""Tests for TASK-024: Graph Orchestrator."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from core.graph import GraphOrchestrator, KnowledgeNode
from runtime.context import ExecutionContext


def test_graph_orchestrator_assembly():
    orch = GraphOrchestrator()
    orch.knowledge_graph.add_node(
        KnowledgeNode(category="Policy", title="Approval Policy", content="Protected actions require confirmation.")
    )

    ctx = ExecutionContext(actor="Owner", role="owner")
    graph_ctx = orch.assemble_graph_context(ctx, goal="Approval Policy")

    assert isinstance(graph_ctx, dict)
    assert graph_ctx["execution_id"] == ctx.execution_id
    assert len(graph_ctx["relevant_knowledge"]) == 1
    assert graph_ctx["relevant_knowledge"][0]["title"] == "Approval Policy"
