"""
Integration tests for browser launch, Cloudflare bypass, and login form visibility.

These tests launch a REAL browser (camoufox) and navigate to the VFS site.
They take ~30–60 seconds each.

Prerequisites (run once on the VPS):
    pip install camoufox[geoip]
    python -m camoufox fetch

Usage:
    cd ~/vfs
    python -m pytest tests/test_browser.py -v -s --timeout=120
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from vfs_appointment_bot.utils.config_reader import get_config_value, initialize_config


@pytest.fixture(autouse=True)
def _init_config():
    initialize_config()


# ── Dependency checks (fast) ─────────────────────────────────────────────────

def test_camoufox_importable():
    """camoufox package must be installed."""
    try:
        import camoufox  # noqa: F401
    except ImportError:
        pytest.fail(
            "camoufox is not installed.\n"
            "Fix: pip install camoufox[geoip] && python -m camoufox fetch"
        )


def test_camoufox_binary_present():
    """camoufox patched Firefox binary must have been downloaded."""
    try:
        from camoufox.sync_api import Camoufox
        with Camoufox(headless=True) as browser:
            _ = browser.new_page()
    except Exception as e:
        msg = str(e)
        if "executable" in msg.lower() or "not found" in msg.lower() or "fetch" in msg.lower():
            pytest.fail(
                "camoufox browser binary is missing.\n"
                "Fix: python -m camoufox fetch"
            )
        pytest.fail(f"Unexpected error launching camoufox: {e}")


# ── Cloudflare bypass test (slow) ────────────────────────────────────────────

@pytest.mark.timeout(120)
def test_no_cloudflare_block():
    """Navigate to the AO-PT VFS login URL and confirm Cloudflare is NOT blocking.

    A Cloudflare challenge page has:
    - An empty page title, OR title containing "Just a moment"
    - OR CF DOM elements like #challenge-running

    This test FAILS if patchright Firefox was being used. It PASSES with camoufox.
    """
    from camoufox.sync_api import Camoufox

    url = get_config_value("vfs-url", "AO-PT")
    assert url, "AO-PT URL not configured"

    with Camoufox(headless=True, geoip=True) as browser:
        page = browser.new_page()
        page.set_default_timeout(30_000)
        # Block fonts to prevent screenshot hangs (same as production)
        page.route("**/*.{woff,woff2,ttf,otf,eot}", lambda r: r.abort())
        page.goto(url)

        title = page.title().lower()
        current_url = page.url

        # Check CF title indicators
        cf_titles = ["just a moment", "attention required", "checking your browser"]
        assert not any(t in title for t in cf_titles), (
            f"Cloudflare block detected!\n"
            f"  Title: '{page.title()}'\n"
            f"  URL: {current_url}\n"
            f"  Hint: Your VPS IP may be in Cloudflare's datacenter block list. "
            f"Consider a residential proxy."
        )

        # Empty title is also a CF block indicator
        assert title != "", (
            f"Page title is empty — Cloudflare JS challenge is blocking.\n"
            f"  URL: {current_url}\n"
            f"  Hint: camoufox may need a residential proxy to bypass this IP block."
        )

        # Check CF DOM selectors
        for sel in ["#challenge-running", "#challenge-stage", "div.cf-turnstile"]:
            el = page.query_selector(sel)
            assert el is None, (
                f"Cloudflare DOM element '{sel}' found — CF challenge is active.\n"
                f"  Title: '{page.title()}', URL: {current_url}"
            )


@pytest.mark.timeout(120)
def test_login_form_visible():
    """The email input must appear within 45s — confirms CF bypass AND page load.

    If this passes, the bot can log in.
    If this fails after test_no_cloudflare_block passes, the email field
    selector may have changed on the VFS site.
    """
    from camoufox.sync_api import Camoufox

    url = get_config_value("vfs-url", "AO-PT")

    with Camoufox(headless=True, geoip=True) as browser:
        page = browser.new_page()
        page.route("**/*.{woff,woff2,ttf,otf,eot}", lambda r: r.abort())
        page.goto(url)

        try:
            page.wait_for_selector('[placeholder="jane.doe@email.com"]', timeout=45_000)
        except Exception:
            pytest.fail(
                "Email input field '[placeholder=\"jane.doe@email.com\"]' did not appear within 45s.\n"
                f"  Current URL: {page.url}\n"
                f"  Page title: '{page.title()}'\n"
                "  Hint: Either CF is blocking, or VFS changed the login form."
            )

        assert page.get_by_placeholder("jane.doe@email.com").is_visible(), (
            "Email input found in DOM but is not visible"
        )
