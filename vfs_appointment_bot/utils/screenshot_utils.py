"""Utility helpers for saving Playwright page screenshots during bot runs.

Screenshots are written to ``<repo_root>/logs/screenshots/`` and named
``<timestamp>_<label>.png``.

Two changes vs. a naive ``page.screenshot()`` call prevent the
``waiting for fonts to load`` hang that occurs on Cloudflare challenge pages:

1. ``PW_TEST_SCREENSHOT_NO_FONTS_READY=1`` environment variable tells the
   Playwright browser bridge to skip the font-ready check entirely.
2. Using a viewport ``clip`` instead of ``full_page=True`` avoids a second
   round of resource loading that can also trigger font waits.

The function is deliberately silent on failure so it never interrupts the
main bot flow.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

# Tell Playwright NOT to wait for fonts before taking a screenshot.
# Must be set before the first playwright import — safe to set here at module
# load time because this module is always imported before the browser launches.
os.environ.setdefault("PW_TEST_SCREENSHOT_NO_FONTS_READY", "1")

# Resolve the repo root: this file lives at
# <repo_root>/vfs_appointment_bot/utils/screenshot_utils.py
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Viewport dimensions used for the clip — matches a typical 1280×800 desktop.
_CLIP = {"x": 0, "y": 0, "width": 1280, "height": 800}


def save_screenshot(page, label: str) -> None:
    """Save a browser viewport screenshot for debugging purposes.

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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = screenshot_dir / f"{timestamp}_{label}.png"
        # clip=viewport avoids full_page resource loading; timeout is a hard cap.
        page.screenshot(path=str(path), clip=_CLIP, timeout=5_000)
        logging.debug("Screenshot saved → %s", path)
    except Exception as exc:
        logging.warning("Could not save screenshot '%s': %s", label, exc)
