"""Tests for TASK-004: Workflow Template System."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.workflow.templates import (
    ApprovalWorkflowTemplate,
    NotificationWorkflowTemplate,
    TaskWorkflowTemplate,
    MeetingWorkflowTemplate,
    CustomerRequestWorkflowTemplate,
)
from runtime.graph import WorkflowGraph, NodeType


def test_approval_workflow_template():
    tmpl = ApprovalWorkflowTemplate()
    assert tmpl.name == "approval_workflow"
    graph = tmpl.build_graph()
    assert isinstance(graph, WorkflowGraph)
    assert "APPROVAL" in graph.nodes
    assert "POLICY" in graph.nodes


def test_notification_workflow_template():
    tmpl = NotificationWorkflowTemplate()
    graph = tmpl.build_graph()
    assert isinstance(graph, WorkflowGraph)
    assert "EXECUTE" in graph.nodes
    assert "VERIFY" in graph.nodes


def test_task_workflow_template():
    tmpl = TaskWorkflowTemplate()
    graph = tmpl.build_graph()
    assert isinstance(graph, WorkflowGraph)
    assert "PLAN" in graph.nodes
    assert "MEMORY" in graph.nodes


def test_meeting_workflow_template():
    tmpl = MeetingWorkflowTemplate()
    graph = tmpl.build_graph()
    assert isinstance(graph, WorkflowGraph)
    assert "CONTEXT" in graph.nodes


def test_customer_request_workflow_template():
    tmpl = CustomerRequestWorkflowTemplate()
    graph = tmpl.build_graph()
    assert isinstance(graph, WorkflowGraph)
    assert "MEMORY" in graph.nodes
