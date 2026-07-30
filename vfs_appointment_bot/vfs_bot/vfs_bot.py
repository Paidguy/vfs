import argparse
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from patchright.sync_api import Page, sync_playwright

from vfs_appointment_bot.notification.notification_client_factory import (
    get_notification_client,
)
from vfs_appointment_bot.utils.config_reader import get_config_value


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
        logging.info(
            "Starting VFS Bot for "
            f"{self.source_country_code.upper()}-{self.destination_country_code.upper()}"
        )

        # ---- Read mandatory configuration --------------------------------
        try:
            browser_type = get_config_value("browser", "type", "firefox")
            headless_raw = get_config_value("browser", "headless", "True")
            url_key = f"{self.source_country_code}-{self.destination_country_code}"
            vfs_url = get_config_value("vfs-url", url_key)
            if vfs_url is None:
                raise KeyError(url_key)
        except KeyError as exc:
            logging.error("Missing configuration value: %s", exc)
            return False

        headless = headless_raw.strip().lower() in ("true", "1", "yes")
        email_id = get_config_value("vfs-credential", "email")
        password = get_config_value("vfs-credential", "password")

        appointment_params = self.get_appointment_params(args)

        # ---- Launch browser ----------------------------------------------
        with sync_playwright() as p:
            browser = getattr(p, browser_type).launch(headless=headless)
            page = browser.new_page()

            # patchright already patches the CDP/WebDriver fingerprint at the
            # binary level — no additional stealth plugin call is required.
            page.set_default_timeout(30_000)
            page.set_default_navigation_timeout(60_000)

            page.goto(vfs_url)
            self.pre_login_steps(page)

            try:
                self.login(page, email_id, password)
                logging.info("Logged in successfully")
            except Exception:
                browser.close()
                raise LoginError(
                    "\033[1;31mLogin failed. "
                    "Please verify your username and password by logging in "
                    "to the browser manually and try again.\033[0m"
                )

            logging.info("Checking appointments for %s", appointment_params)
            appointment_found = False
            try:
                dates = self.check_for_appointment(page, appointment_params)
                if dates:
                    logging.info(
                        "\033[1;32mFound appointments on: %s\033[0m",
                        ", ".join(dates),
                    )
                    self.notify_appointment(appointment_params, dates)
                    appointment_found = True
                else:
                    logging.info(
                        "\033[1;33mNo appointments found for the specified criteria.\033[0m"
                    )
            except Exception as exc:
                logging.error("Appointment check failed: %s", exc)

            browser.close()
            return appointment_found

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def get_appointment_params(self, args: argparse.Namespace) -> Dict[str, str]:
        """Collect appointment parameters from CLI args or interactive prompts.

        Iterates over :attr:`appointment_param_keys` and resolves each value
        from the ``--appointment-params`` argument if provided, or falls back
        to an interactive ``input()`` prompt.

        Args:
            args: Parsed CLI arguments.

        Returns:
            A dictionary mapping each appointment parameter key to its value.
        """
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
        """Dispatch appointment notifications to all configured channels.

        Args:
            appointment_params: The search criteria used (logged in the message).
            dates: The available appointment date strings found.
        """
        criteria = ", ".join(appointment_params.values())
        message = f"Found appointment(s) for {criteria} on {', '.join(dates)}"

        channels_raw = get_config_value("notification", "channels", "")
        if not channels_raw.strip():
            logging.warning(
                "No notification channels configured — skipping notification."
            )
            return

        for channel in channels_raw.split(","):
            client = get_notification_client(channel)
            try:
                client.send_notification(message)
            except Exception as exc:
                logging.error("Failed to send %s notification: %s", channel.strip(), exc)

    # ------------------------------------------------------------------
    # Shared pre-login helper
    # ------------------------------------------------------------------

    def _reject_cookies_if_present(self, page: Page) -> None:
        """Attempt to dismiss a cookie-consent banner if one is visible.

        Uses a short timeout so the method never blocks if there is no banner.
        Silently swallows the timeout exception — the bot continues regardless.

        Args:
            page: The Playwright page object.
        """
        try:
            page.get_by_role("button", name=self._REJECT_COOKIE_RE).click(timeout=3_000)
            logging.debug("Rejected cookie consent banner.")
        except Exception:
            pass  # No banner present — nothing to do.

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def login(self, page: Page, email_id: str, password: str) -> None:
        """Perform the country-specific VFS login sequence.

        Subclasses must fill the login form and wait for a reliable
        post-login signal before returning.

        Args:
            page: The Playwright page object.
            email_id: VFS account email address.
            password: VFS account password.

        Raises:
            Exception: If login cannot be confirmed (caught and re-raised as
                :class:`LoginError` by :meth:`run`).
        """

    @abstractmethod
    def pre_login_steps(self, page: Page) -> None:
        """Perform any actions required *before* the login form is submitted.

        Examples include accepting/rejecting cookie banners, selecting a
        language, or waiting for a Cloudflare challenge to auto-resolve.

        Args:
            page: The Playwright page object.
        """

    @abstractmethod
    def check_for_appointment(
        self, page: Page, appointment_params: Dict[str, str]
    ) -> Optional[List[str]]:
        """Check the VFS booking form for available appointments.

        Subclasses must navigate the post-login booking flow, apply the
        filters specified by ``appointment_params``, and return the list of
        available date strings.

        Args:
            page: The Playwright page object.
            appointment_params: Booking filter criteria (e.g. visa centre,
                category, sub-category).

        Returns:
            A non-empty list of date strings if slots are found, or ``None``
            / an empty list when none are available.
        """
