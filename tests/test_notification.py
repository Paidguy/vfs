"""
Integration tests for Telegram notification sending.
Sends a REAL Telegram message — check your phone/desktop to confirm receipt.

Usage:
    cd ~/vfs
    python -m pytest tests/test_notification.py -v -s
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from vfs_appointment_bot.utils.config_reader import get_config_section, initialize_config
from vfs_appointment_bot.notification.telegram_client import TelegramClient


@pytest.fixture(autouse=True)
def _init_config():
    initialize_config()


def test_telegram_client_initialises():
    """TelegramClient must initialise and read config without raising."""
    client = TelegramClient()
    assert client.config.get("bot_token"), "bot_token missing from client config"
    assert client.config.get("chat_id"), "chat_id missing from client config"
    assert client.config.get("parse_mode"), "parse_mode missing from client config"


def test_telegram_sends_real_message():
    """Send an actual message via the Telegram Bot API.

    ✅ Check your Telegram — you should receive:
    '🧪 VFS Bot — Test Notification ...'
    """
    client = TelegramClient()
    # This will raise requests.HTTPError if the token/chat_id are wrong.
    client.send_notification(
        "🧪 *VFS Bot — Test Notification*\n"
        "Automated test run\\. If you see this, Telegram is working correctly\\."
    )


def test_telegram_rejects_bad_token(monkeypatch):
    """TelegramClient must raise on HTTP error when token is invalid."""
    import requests

    initialize_config()
    client = TelegramClient()
    # Patch the bot token to an invalid value
    monkeypatch.setitem(client.config, "bot_token", "000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

    with pytest.raises(requests.HTTPError):
        client.send_notification("This should fail")
