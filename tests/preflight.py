#!/usr/bin/env python
"""
VFS Bot Pre-flight Check
========================
Quick sanity check that verifies all dependencies and config are correct
BEFORE running the main bot. No pytest needed.

Usage:
    cd ~/vfs
    python tests/preflight.py

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""
import os
import sys

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def chk(name: str, fn) -> None:
    """Run a named check function and record pass/fail."""
    try:
        fn()
        print(f"  ✅  {name}")
        _results.append(True)
    except Exception as exc:
        print(f"  ❌  {name}")
        print(f"        → {exc}")
        _results.append(False)


def _require(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


# ── Run checks ───────────────────────────────────────────────────────────────

print("\n🔍  VFS Bot Pre-flight Check")
print("=" * 50)

# 1. Config
print("\n[1/4] Configuration")
from vfs_appointment_bot.utils.config_reader import (
    initialize_config, get_config_value, get_config_section
)
initialize_config()

chk("Config loads", lambda: None)

chk("VFS email set", lambda: _require(
    get_config_value("vfs-credential", "email") not in (None, "", "email"),
    f"VFS email is a placeholder: '{get_config_value('vfs-credential', 'email')}'"
))

chk("VFS password set", lambda: _require(
    get_config_value("vfs-credential", "password") not in (None, "", "password"),
    "VFS password is a placeholder"
))

chk("AO-PT URL present", lambda: _require(
    bool(get_config_value("vfs-url", "AO-PT")),
    "Missing [vfs-url] AO-PT"
))

chk("Notification = telegram", lambda: _require(
    "telegram" in (get_config_value("notification", "channels") or "").lower(),
    f"Expected telegram, got: '{get_config_value('notification', 'channels')}'"
))

chk("Browser type = camoufox", lambda: _require(
    get_config_value("browser", "type") == "camoufox",
    f"Expected camoufox, got: '{get_config_value('browser', 'type')}'"
))

# 2. Dependencies
print("\n[2/4] Dependencies")

chk("camoufox importable", lambda: __import__("camoufox"))

chk("camoufox binary present", _check_camoufox_binary := lambda: _verify_camoufox())

chk("patchright importable (fallback)", lambda: __import__("patchright"))

chk("requests importable", lambda: __import__("requests"))

chk("tqdm importable", lambda: __import__("tqdm"))

# 3. Telegram
print("\n[3/4] Telegram Notification")

chk("Telegram client initialises", _check_telegram_init := lambda: _init_telegram())

chk("Telegram sends test message", lambda: _send_telegram_test())

# 4. Logging
print("\n[4/4] Logging / Filesystem")

chk("logs/ directory writable", lambda: _check_logs_dir())

# ── Summary ──────────────────────────────────────────────────────────────────

print("\n" + "=" * 50)
passed = sum(_results)
total = len(_results)
if all(_results):
    print(f"✅  All {total} checks passed — bot is ready to run!\n")
    print("Run:")
    print('  python run.py -sc ao -dc pt \\')
    print('    -ap "visa_center=Angola – Luanda,visa_category=Nacional,visa_sub_category=Nacional"')
else:
    print(f"❌  {total - passed}/{total} checks FAILED — fix the issues above before running the bot.\n")

sys.exit(0 if all(_results) else 1)


# ── Helper functions ─────────────────────────────────────────────────────────

def _verify_camoufox():
    from camoufox.sync_api import Firefox
    try:
        with Firefox(headless=True) as b:
            b.new_page()
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("executable", "not found", "fetch", "download")):
            raise RuntimeError(
                "camoufox binary missing.\n"
                "        Fix: python -m camoufox fetch"
            ) from e
        raise


def _init_telegram():
    from vfs_appointment_bot.notification.telegram_client import TelegramClient
    client = TelegramClient()
    _require(bool(client.config.get("bot_token")), "bot_token empty")
    _require(bool(client.config.get("chat_id")), "chat_id empty")


def _send_telegram_test():
    from vfs_appointment_bot.notification.telegram_client import TelegramClient
    TelegramClient().send_notification(
        "🔍 *VFS Bot Pre-flight Check*\n"
        "All systems go\\. This is a test message\\."
    )


def _check_logs_dir():
    import tempfile
    from pathlib import Path
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    test_file = logs_dir / ".preflight_write_test"
    test_file.write_text("ok")
    test_file.unlink()


if __name__ == "__main__":
    pass  # All code runs at module level above
