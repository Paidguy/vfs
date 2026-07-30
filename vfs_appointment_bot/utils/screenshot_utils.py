"""Utility helpers for saving Playwright page screenshots during bot runs.

Screenshots are written to ``<repo_root>/logs/screenshots/`` and named
``<timestamp>_<label>.png``.  The function is deliberately silent on
failure so it never interrupts the main bot flow.
"""

import logging
from datetime import datetime
from pathlib import Path

# Resolve the repo root: this file lives at
# <repo_root>/vfs_appointment_bot/utils/screenshot_utils.py
# so repo_root = __file__.parent.parent.parent
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def save_screenshot(page, label: str) -> None:
    """Save a browser screenshot for debugging purposes.

    Captures the current state of ``page`` and writes it to
    ``<repo_root>/logs/screenshots/<timestamp>_<label>.png``.

    Args:
        page: A Playwright ``Page`` object (sync or async).
        label: A short, filesystem-safe string identifying what this
               screenshot represents (e.g. ``"login_failed"``).
    """
    screenshot_dir = _REPO_ROOT / "logs" / "screenshots"
    try:
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # ms precision
        path = screenshot_dir / f"{timestamp}_{label}.png"
        page.screenshot(path=str(path), full_page=True)
        logging.debug("Screenshot saved → %s", path)
    except Exception as exc:
        logging.warning("Could not save screenshot '%s': %s", label, exc)
