"""
Unit tests for config loading and validation.
No browser, no network — runs in ~1 second.

Usage:
    cd ~/vfs
    python -m pytest tests/test_config.py -v
"""
import os
import sys

# Ensure the repo root is on sys.path so the package resolves without pip install.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from vfs_appointment_bot.utils.config_reader import (
    get_config_section,
    get_config_value,
    initialize_config,
)


@pytest.fixture(autouse=True)
def _init_config():
    """Initialize config before every test in this module."""
    initialize_config()


# ── Config loading ──────────────────────────────────────────────────────────

def test_config_loads_without_error():
    """initialize_config() must complete without raising."""
    # autouse fixture already called it — if we're here it succeeded.


def test_interval_is_numeric():
    val = get_config_value("default", "interval")
    assert val is not None, "Missing [default] interval"
    assert val.strip().isdigit(), f"interval must be a number, got: {val}"


# ── VFS credentials ─────────────────────────────────────────────────────────

def test_vfs_email_not_placeholder():
    email = get_config_value("vfs-credential", "email")
    assert email not in (None, "", "email"), (
        f"VFS email is missing or still a placeholder: '{email}'"
    )
    assert "@" in email, f"VFS email doesn't look like an email address: '{email}'"


def test_vfs_password_not_placeholder():
    pwd = get_config_value("vfs-credential", "password")
    assert pwd not in (None, "", "password"), (
        f"VFS password is missing or still a placeholder: '{pwd}'"
    )


# ── VFS URLs ────────────────────────────────────────────────────────────────

def test_ao_pt_url_present_and_valid():
    url = get_config_value("vfs-url", "AO-PT")
    assert url is not None, "Missing [vfs-url] AO-PT key"
    assert url.startswith("https://"), f"AO-PT URL must use HTTPS, got: '{url}'"
    assert "vfsglobal.com" in url, f"Unexpected domain in AO-PT URL: '{url}'"


# ── Telegram ────────────────────────────────────────────────────────────────

def test_telegram_bot_token_not_placeholder():
    token = get_config_section("telegram").get("bot_token")
    assert token not in (None, "", "bot_token"), (
        f"Telegram bot_token is missing or a placeholder: '{token}'"
    )
    # A real Telegram token looks like 123456789:AAH...
    assert ":" in token, f"Telegram bot_token format invalid (expected <id>:<hash>): '{token}'"


def test_telegram_chat_id_not_placeholder():
    chat_id = get_config_section("telegram").get("chat_id")
    assert chat_id not in (None, "", "chat_id"), (
        f"Telegram chat_id is missing or a placeholder: '{chat_id}'"
    )
    assert chat_id.strip().lstrip("-").isdigit(), (
        f"Telegram chat_id must be numeric, got: '{chat_id}'"
    )


# ── Notification channel ────────────────────────────────────────────────────

def test_notification_channel_includes_telegram():
    channels = get_config_value("notification", "channels", "")
    assert "telegram" in channels.lower(), (
        f"Expected 'telegram' in notification channels, got: '{channels}'"
    )


# ── Browser config ──────────────────────────────────────────────────────────

def test_browser_type_is_camoufox():
    bt = get_config_value("browser", "type", "firefox")
    assert bt == "camoufox", (
        f"Browser type should be 'camoufox' for Cloudflare bypass, got: '{bt}'"
    )
