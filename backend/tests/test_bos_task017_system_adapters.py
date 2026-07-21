"""Tests for TASK-017: System Adapters."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from adapters import AdapterRequest
from adapters.system import CalendarAdapter, VoiceAdapter, PaymentsAdapter, StorageAdapter


def test_calendar_adapter():
    ad = CalendarAdapter()
    assert ad.connect() is True
    req = AdapterRequest(action="schedule", payload={"title": "Team Sync", "time": "2026-07-21 10:00"})
    res = ad.execute_request(req)
    assert res.success is True
    assert res.data["channel"] == "calendar"


def test_voice_adapter():
    ad = VoiceAdapter()
    assert ad.connect() is True
    req = AdapterRequest(action="call", recipient="9876543210")
    res = ad.execute_request(req)
    assert res.success is True
    assert res.data["channel"] == "voice"


def test_payments_adapter():
    ad = PaymentsAdapter()
    assert ad.connect() is True
    req = AdapterRequest(action="charge", payload={"amount": 500.0, "currency": "INR"})
    res = ad.execute_request(req)
    assert res.success is True
    assert res.data["amount"] == 500.0


def test_storage_adapter():
    ad = StorageAdapter()
    assert ad.connect() is True
    req = AdapterRequest(action="upload", payload={"path": "report.pdf"})
    res = ad.execute_request(req)
    assert res.success is True
    assert res.data["storage_path"] == "report.pdf"
