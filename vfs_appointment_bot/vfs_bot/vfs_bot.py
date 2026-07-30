import argparse
import logging
import re
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Callable, Dict, List, Optional, Tuple

from vfs_appointment_bot.notification.notification_client_factory import (
    get_notification_client,
)
from vfs_appointment_bot.utils.config_reader import get_config_value
from vfs_appointment_bot.utils.screenshot_utils import save_screenshot


class LoginError(Exception):
    """Raised when the VFS login step fails."""


class VfsBot(ABC):
    """Abstract base class for all country-specific VFS bots.

    Provides shared logic for browser launch, login, appointment checking,
    and notification dispatch. Subclasses implement the three abstract methods
    to handle country-specific website behaviour:

    - :meth:`login`
    - :meth:`pre_login_steps`
    - :meth:`check_for_appointment`
    """

    # Regex patterns for common UI text that is stable across VFS Angular apps.
    _REJECT_COOKIE_RE = re.compile(r"Reject All", re.IGNORECASE)
    _START_BOOKING_RE = re.compile(r"Start New Booking", re.IGNORECASE)

    def __init__(self) -> None:
        """Initialise a VfsBot instance."""
        self.source_country_code: Optional[str] = None
        self.destination_country_code: Optional[str] = None
        self.appointment_param_keys: List[str] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, args: argparse.Namespace = None) -> bool:
        """Run one full appointment-check cycle.

        Launches a browser, navigates to the VFS login page, logs in,
        checks for available appointments, sends a notification if any are
        found, and closes the browser.

        Args:
            args: Parsed CLI arguments (see :mod:`main`).

        Returns:
            ``True`` if at least one appointment was found; ``False``
            otherwise (including on soft errors such as a missing config key).
        """
        route = f"{self.source_country_code.upper()}-{self.destination_country_code.upper()}"
        logging.info("Starting VFS Bot for %s", route)

        # ---- Read mandatory configuration --------------------------------
        try:
            browser_type = get_config_value("browser", "type", "camoufox")
            headless_raw = get_config_value("browser", "headless", "True")
            url_key = f"{self.source_country_code}-{self.destination_country_code}"
            vfs_url = get_config_value("vfs-url", url_key)
            if vfs_url is None:
                raise KeyError(url_key)
        except KeyError as exc:
            logging.error("Missing configuration value for key: %s", exc)
            return False

        headless = headless_raw.strip().lower() in ("true", "1", "yes")
        email_id = get_config_value("vfs-credential", "email")
        password = get_config_value("vfs-credential", "password")

        logging.debug(
            "Config loaded — browser=%s headless=%s url=%s email=%s",
            browser_type, headless, vfs_url, email_id,
        )

        appointment_params = self.get_appointment_params(args)
        logging.debug("Appointment params resolved: %s", appointment_params)

        # ---- Launch browser ----------------------------------------------
        logging.info("Launching browser (type=%s headless=%s)", browser_type, headless)
        with self._browser_context(browser_type, headless) as page:

            page.set_default_timeout(30_000)
            page.set_default_navigation_timeout(60_000)

            # Block web font requests so screenshots never hang on font-load.
            page.route(
                "**/*.{woff,woff2,ttf,otf,eot}",
                lambda route: route.abort(),
            )
            logging.debug("Font request blocking enabled")

            # ---- Navigate ------------------------------------------------
            logging.info("Navigating to %s", vfs_url)
            page.goto(vfs_url)
            logging.debug("Page title after navigation: '%s'", page.title())
            logging.debug("Current URL: %s", page.url)

            # ---- Cloudflare detection ------------------------------------
            if self._is_cloudflare_blocked(page):
                logging.error(
                    "CLOUDFLARE BLOCK DETECTED — title='%s' url='%s'. "
                    "camoufox should bypass this. If it persists, a residential proxy is needed.",
                    page.title(), page.url,
                )
                save_screenshot(page, "00_cloudflare_blocked")
                # Still attempt to wait — camoufox may resolve it shortly
                logging.info("Waiting up to 30s for Cloudflare to self-resolve …")
                try:
                    page.wait_for_function(
                        """() => {
                            const t = document.title.toLowerCase();
                            return !t.includes('just a moment') &&
                                   !t.includes('checking your browser') &&
                                   t !== '';
                        }""",
                        timeout=30_000,
                    )
                    logging.info("Cloudflare resolved — real page now loading")
                except Exception:
                    logging.error("Cloudflare did not resolve — login will likely fail")
            else:
                logging.info("No Cloudflare block detected — page loaded cleanly")

            save_screenshot(page, "01_landing_page")

            # ---- Pre-login steps -----------------------------------------
            logging.debug("Running pre-login steps")
            self.pre_login_steps(page)
            save_screenshot(page, "02_after_pre_login_steps")

            # ---- Login ---------------------------------------------------
            try:
                logging.info("Attempting login with email: %s", email_id)
                self.login(page, email_id, password)
                logging.info("Login successful — current URL: %s", page.url)
                save_screenshot(page, "03_post_login")
            except Exception as login_exc:
                logging.debug("Login exception (full traceback):", exc_info=True)
                save_screenshot(page, "04_login_failed")
                raise LoginError(
                    f"Login failed [{type(login_exc).__name__}: {login_exc}]. "
                    "Please verify your credentials by logging in manually."
                ) from login_exc

            # ---- Appointment check ---------------------------------------
            logging.info("Checking appointments for params: %s", appointment_params)
            appointment_found = False
            try:
                dates = self.check_for_appointment(page, appointment_params)
                if dates:
                    logging.info("FOUND appointments on: %s", ", ".join(dates))
                    self.notify_appointment(appointment_params, dates)
                    appointment_found = True
                else:
                    logging.info("No appointments found for the specified criteria.")
            except Exception as exc:
                logging.error("Appointment check failed: %s", exc, exc_info=True)
                save_screenshot(page, "05_appointment_check_failed")

        logging.info("Browser closed — cycle complete. appointment_found=%s", appointment_found)
        return appointment_found

    # ------------------------------------------------------------------
    # Browser launcher
    # ------------------------------------------------------------------

    @staticmethod
    @contextmanager
    def _browser_context(browser_type: str, headless: bool):
        """Context manager that yields a ready Playwright Page object.

        Tries ``camoufox`` first (best Cloudflare bypass). Falls back to
        ``patchright`` for any other browser type or if camoufox is unavailable.

        Args:
            browser_type: ``"camoufox"``, ``"firefox"``, ``"chromium"``, or ``"webkit"``.
            headless: Whether to run the browser without a visible window.

        Yields:
            A Playwright-compatible ``Page`` instance.
        """
        if browser_type == "camoufox":
            try:
                from camoufox.sync_api import Camoufox
                logging.info("Using camoufox (Cloudflare-resistant Firefox)")
                with Camoufox(headless=headless, geoip=True) as browser:
                    page = browser.new_page()
                    yield page
                return
            except ImportError:
                logging.warning(
                    "camoufox is not installed — falling back to patchright firefox. "
                    "Install it with: pip install camoufox[geoip] && python -m camoufox fetch"
                )
                browser_type = "firefox"

        # patchright fallback
        from patchright.sync_api import sync_playwright
        logging.info("Using patchright %s", browser_type)
        with sync_playwright() as p:
            browser = getattr(p, browser_type).launch(headless=headless)
            page = browser.new_page()
            try:
                yield page
            finally:
                browser.close()

    # ------------------------------------------------------------------
    # Cloudflare detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_cloudflare_blocked(page) -> bool:
        """Return ``True`` if the current page appears to be a Cloudflare challenge.

        Checks title text, URL markers, and known CF DOM selectors.

        Args:
            page: A Playwright ``Page`` object.

        Returns:
            ``True`` if a Cloudflare challenge is detected, ``False`` otherwise.
        """
        title = page.title().lower()
        url = page.url

        # Empty title or known CF challenge titles
        cf_titles = ["just a moment", "attention required", "checking your browser"]
        if title == "" or any(t in title for t in cf_titles):
            logging.debug("CF detected via title: '%s'", title)
            return True

        # CF URL markers
        if "/__cf_chl_rt_tk=" in url or "/cdn-cgi/challenge-platform/" in url:
            logging.debug("CF detected via URL marker: %s", url)
            return True

        # CF DOM selectors
        for sel in ["#challenge-running", "#challenge-stage", "#challenge-form",
                    "div.cf-turnstile", "iframe[src*='challenges.cloudflare.com']"]:
            try:
                if page.query_selector(sel):
                    logging.debug("CF detected via DOM selector: %s", sel)
                    return True
            except Exception:
                pass

        return False

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def get_appointment_params(self, args: argparse.Namespace) -> Dict[str, str]:
        """Collect appointment parameters from CLI args or interactive prompts."""
        appointment_params: Dict[str, str] = {}
        provided = getattr(args, "appointment_params", None) or {}
        for key in self.appointment_param_keys:
            if provided.get(key):
                appointment_params[key] = provided[key]
            else:
                key_label = key.replace("_", " ")
                appointment_params[key] = input(f"Enter the {key_label}: ")
        return appointment_params

    def notify_appointment(
        self, appointment_params: Dict[str, str], dates: List[str]
    ) -> None:
        """Dispatch appointment notifications to all configured channels."""
        criteria = ", ".join(appointment_params.values())
        message = f"Found appointment(s) for {criteria} on {', '.join(dates)}"
        logging.debug("Notification message: %s", message)

        channels_raw = get_config_value("notification", "channels", "")
        if not channels_raw.strip():
            logging.warning("No notification channels configured — skipping notification.")
            return

        for channel in channels_raw.split(","):
            channel = channel.strip()
            logging.debug("Sending notification via channel: %s", channel)
            client = get_notification_client(channel)
            try:
                client.send_notification(message)
                logging.info("Notification sent via %s", channel)
            except Exception as exc:
                logging.error(
                    "Failed to send %s notification: %s", channel, exc, exc_info=True
                )

    def _reject_cookies_if_present(self, page) -> None:
        """Attempt to dismiss a cookie-consent banner if one is visible."""
        try:
            page.get_by_role("button", name=self._REJECT_COOKIE_RE).click(timeout=3_000)
            logging.debug("Rejected cookie consent banner.")
        except Exception:
            logging.debug("No cookie consent banner found (or already dismissed).")

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def login(self, page, email_id: str, password: str) -> None:
        """Perform the country-specific VFS login sequence."""

    @abstractmethod
    def pre_login_steps(self, page) -> None:
        """Perform any actions required *before* the login form is submitted."""

    @abstractmethod
    def check_for_appointment(
        self, page, appointment_params: Dict[str, str]
    ) -> Optional[List[str]]:
        """Check the VFS booking form for available appointments."""
