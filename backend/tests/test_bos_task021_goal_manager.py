"""Tests for TASK-021: Goal Manager."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from runtime.goals import GoalManager, Goal, GoalState


def setup_function():
    GoalManager.clear()


def test_goal_creation_and_breakdown():
    goal = GoalManager.create_goal(
        title="Launch Regional Branch Office",
        description="Expand business operations to Orai region",
    )
    assert isinstance(goal, Goal)
    assert goal.state == GoalState.IN_PROGRESS
    assert len(goal.milestones) == 4
    assert len(goal.execution_units) == 4
    assert goal.progress_percentage == 0.0


def test_goal_progress_tracking():
    goal = GoalManager.create_goal(title="System Deployment")
    goal_id = goal.goal_id

    # Mark 2 units completed out of 4 (50%)
    GoalManager.update_progress(goal_id, "u1", "COMPLETED")
    updated = GoalManager.update_progress(goal_id, "u2", "COMPLETED")

    assert updated.progress_percentage == 50.0
    assert updated.state == GoalState.IN_PROGRESS

    # Complete remaining units (100%)
    GoalManager.update_progress(goal_id, "u3", "COMPLETED")
    final_goal = GoalManager.update_progress(goal_id, "u4", "COMPLETED")

    assert final_goal.progress_percentage == 100.0
    assert final_goal.state == GoalState.COMPLETED
