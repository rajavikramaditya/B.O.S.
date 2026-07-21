"""B.O.S. Workflow Templates Package v0.1

Provides reusable graph templates for runtime execution workflows:
- base
- approval
- notification
- task
- meeting
- customer_request
"""

from .base import BaseWorkflowTemplate
from .approval import ApprovalWorkflowTemplate
from .notification import NotificationWorkflowTemplate
from .task import TaskWorkflowTemplate
from .meeting import MeetingWorkflowTemplate
from .customer_request import CustomerRequestWorkflowTemplate

__all__ = [
    "BaseWorkflowTemplate",
    "ApprovalWorkflowTemplate",
    "NotificationWorkflowTemplate",
    "TaskWorkflowTemplate",
    "MeetingWorkflowTemplate",
    "CustomerRequestWorkflowTemplate",
]
