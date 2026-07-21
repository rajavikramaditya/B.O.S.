"""Tests for TASK-016: Messaging Adapters."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from adapters import AdapterRequest, AdapterStatus
from adapters.messaging import WhatsAppAdapter, TelegramAdapter, EmailAdapter


def test_whatsapp_adapter():
    ad = WhatsAppAdapter()
    assert ad.connect() is True
    req = AdapterRequest(action="send", recipient="919999999999", payload={"text": "Hello WhatsApp"})
    res = ad.execute_request(req)
    assert res.success is True
    assert res.data["channel"] == "whatsapp"


def test_telegram_adapter():
    ad = TelegramAdapter()
    assert ad.connect() is True
    req = AdapterRequest(action="send", recipient="chat_123", payload={"text": "Hello Telegram"})
    res = ad.execute_request(req)
    assert res.success is True
    assert res.data["channel"] == "telegram"


def test_email_adapter():
    ad = EmailAdapter()
    assert ad.connect() is True
    req = AdapterRequest(action="send", recipient="user@example.com", payload={"subject": "Test", "text": "Hello Email"})
    res = ad.execute_request(req)
    assert res.success is True
    assert res.data["channel"] == "email"
