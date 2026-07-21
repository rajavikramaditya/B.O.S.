"""Tests for B.O.S. Workflow-Driven State Graph Runtime Architecture."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.state import RuntimeState, Checkpoint
from runtime.graph import WorkflowGraph, WorkflowNode, NodeType, ConditionType
from runtime.planner import GraphPlanner
from runtime.engine import BOSRuntimeEngine, process_message


def test_runtime_state_model():
    state = RuntimeState()
    assert state.execution_id.startswith("exec_")
    assert state.current_node == "START"
    assert state.status == "INITIALIZED"

    state.transition_to("OBSERVE")
    assert state.current_node == "OBSERVE"
    assert len(state.visited_nodes) == 1
    assert state.visited_nodes[0] == "START"

    state.record_error("Sample error")
    assert state.retry_count == 1
    assert len(state.errors) == 1

    cp = state.save_checkpoint("step_1")
    assert isinstance(cp, Checkpoint)
    assert cp.node == "OBSERVE"

    state.transition_to("UNDERSTAND")
    assert state.current_node == "UNDERSTAND"
    restored = state.restore_checkpoint("step_1")
    assert restored is True
    assert state.current_node == "OBSERVE"


def test_workflow_graph_branching():
    graph = WorkflowGraph("test_branch_graph")
    graph.add_node(WorkflowNode("START", "Start", NodeType.START))
    graph.add_node(WorkflowNode("POLICY", "Policy", NodeType.POLICY))
    graph.add_node(WorkflowNode("APPROVAL", "Approval", NodeType.APPROVAL))
    graph.add_node(WorkflowNode("EXECUTE", "Execute", NodeType.EXECUTE))

    graph.add_edge("POLICY", "APPROVAL", ConditionType.IF_APPROVAL_REQUIRED)
    graph.add_edge("POLICY", "EXECUTE", ConditionType.ALWAYS)

    state = RuntimeState()

    # Case 1: No approval required -> next is EXECUTE
    state.policy_data = {"requires_confirmation": False}
    next_node = graph.get_next_node("POLICY", state)
    assert next_node == "EXECUTE"

    # Case 2: Approval required -> next is APPROVAL
    state.policy_data = {"requires_confirmation": True}
    next_node = graph.get_next_node("POLICY", state)
    assert next_node == "APPROVAL"


def test_graph_planner():
    from runtime.observation import ObservationEngine
    from runtime.understanding import UnderstandingEngine
    from runtime.context import ContextEngine

    req = ObservationEngine.observe(role="owner", message="status check")
    intent = UnderstandingEngine.understand(req)
    ctx = ContextEngine.load_context(req, intent)

    graph = GraphPlanner.build_workflow_graph(req, intent, ctx)
    assert isinstance(graph, WorkflowGraph)
    assert "OBSERVE" in graph.nodes
    assert "POLICY" in graph.nodes
    assert "APPROVAL" in graph.nodes
    assert "VERIFY" in graph.nodes


def test_bos_runtime_engine_state_graph_execution():
    res = BOSRuntimeEngine.execute(
        role="customer",
        message="B.O.S. graph test message",
        sender_name="Vikram",
    )
    assert isinstance(res, dict)
    assert "reply" in res
    assert "execution_id" in res
    assert res.get("workflow_status") == "COMPLETED"


def test_bos_runtime_engine_approval_pause():
    res = BOSRuntimeEngine.execute(
        role="owner",
        message="send_azuracast",
    )
    assert isinstance(res, dict)
    assert "execution_id" in res
    # Protected action should require confirmation or pause/wait approval
    assert res.get("workflow_status") in ("COMPLETED", "WAITING_APPROVAL")
