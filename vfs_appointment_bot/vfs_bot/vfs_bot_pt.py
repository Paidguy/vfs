import logging
import re
from typing import Dict, List, Optional

from patchright.sync_api import Page

from vfs_appointment_bot.utils.date_utils import extract_date_from_string
from vfs_appointment_bot.utils.screenshot_utils import save_screenshot
from vfs_appointment_bot.vfs_bot.vfs_bot import VfsBot

# ── Label / button text constants ─────────────────────────────────────────────
# Confirmed from live screenshots of visa.vfsglobal.com/ago/en/prt/login.
# The Sign In button is labelled "Sign In" in the English locale. The Portuguese
# locale path (/ago/pt/prt/) may render "Iniciar Sessão" — the regex covers both.
_SIGN_IN_RE = re.compile(r"Sign In|Iniciar Sess[aã]o", re.IGNORECASE)

# Covers both the pre-login "Book now" CTA and the post-login "Start New Booking"
# button on different VFS platform versions.
_START_BOOKING_RE = re.compile(
    r"Book now|Start New Booking|Iniciar Nova (Marca[cç][aã]o|Reserva)",
    re.IGNORECASE,
)


class VfsBotPt(VfsBot):
    """VFS bot implementation for Portugal (PT) as destination country.

    Handles login, cookie-consent dismissal, and appointment checking for the
    VFS Global Portugal portal (``visa.vfsglobal.com/ago/en/prt/...``).

    .. warning::
        The **login** step is confirmed against live screenshots of the AO-PT
        site. The **check_for_appointment** step uses robust multi-strategy
        selectors with screenshot capture at every step so failures can be
        diagnosed from the saved images.
    """

    def __init__(self, source_country_code: str) -> None:
        """Initialise VfsBotPt.

        Args:
            source_country_code: ISO 3166-1 alpha-2 code of the applicant's
                country (e.g. ``"AO"`` for Angola).
        """
        super().__init__()
        self.source_country_code = source_country_code
        self.destination_country_code = "PT"
        self.appointment_param_keys = [
            "visa_center",
            "visa_category",
            "visa_sub_category",
        ]

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    def pre_login_steps(self, page: Page) -> None:
        """Attempt to dismiss a cookie-consent banner (best-effort).

        No cookie banner was observed on the AO-PT site during testing, but
        this tolerant check is kept in case VFS adds one in a future update.
        It uses a short timeout and swallows any exception so it never
        blocks a run.

        Args:
            page: The Playwright page object.
        """
        logging.debug("pre_login_steps: checking for cookie consent banner")
        try:
            page.get_by_role(
                "button",
                name=re.compile(r"Reject All|Rejeitar", re.IGNORECASE),
            ).click(timeout=3_000)
            logging.debug("Cookie consent banner dismissed.")
        except Exception:
            logging.debug("No cookie consent banner found (or timed out — continuing).")

    def login(self, page: Page, email_id: str, password: str) -> None:
        """Log in to the Angola→Portugal VFS portal.

        Confirmed against live screenshots:
        - Email field: placeholder ``"jane.doe@email.com"``
        - Password field: labelled ``"Password"`` (not "Confirm Password",
          which only appears on the registration page)
        - Submit button: labelled ``"Sign In"``
        - A Cloudflare Turnstile widget must auto-resolve to "Success" before
          the Sign In button becomes clickable. We give it up to 10 seconds.

        Args:
            page: The Playwright page object.
            email_id: VFS account email address.
            password: VFS account password.

        Raises:
            Exception: If the page URL does not change away from ``/login``
                within 30 seconds, indicating a failed login.
        """
        logging.debug("Filling email field with placeholder 'jane.doe@email.com'")
        page.get_by_placeholder("jane.doe@email.com").fill(email_id)

        logging.debug("Filling password field")
        page.get_by_label(
            re.compile(r"^Password\*?$"), exact=False
        ).fill(password)

        # Allow Cloudflare Turnstile time to auto-resolve before clicking.
        logging.debug("Waiting 10s for Cloudflare Turnstile to auto-resolve …")
        page.wait_for_timeout(10_000)
        save_screenshot(page, "login_before_submit")

        logging.debug("Clicking Sign In button")
        page.get_by_role("button", name=_SIGN_IN_RE).click()

        logging.debug("Waiting for URL to leave /login (up to 30s) …")
        page.wait_for_function(
            "() => !window.location.pathname.endsWith('/login')",
            timeout=30_000,
        )
        logging.debug("Login URL check passed — new URL: %s", page.url)

    def check_for_appointment(
        self, page: Page, appointment_params: Dict[str, str]
    ) -> Optional[List[str]]:
        """Navigate the PT booking form and extract available dates.

        Uses multiple selector strategies with a screenshot at each step so
        failures can be diagnosed from the saved images.

        Steps:
        1. Click "Start New Booking" / "Book now" CTA
        2. Select Visa Centre from dropdown
        3. Select Visa Category from dropdown
        4. Select Visa Sub-Category from dropdown
        5. Wait for date availability indicators and extract dates

        Args:
            page: The Playwright page object.
            appointment_params: Must contain ``"visa_center"``,
                ``"visa_category"``, and ``"visa_sub_category"``.

        Returns:
            A list of date strings if slots are available, or ``None``.
        """
        visa_center = appointment_params.get("visa_center", "")
        visa_category = appointment_params.get("visa_category", "")
        visa_sub_category = appointment_params.get("visa_sub_category", "")

        logging.debug(
            "check_for_appointment: center='%s' category='%s' sub='%s'",
            visa_center, visa_category, visa_sub_category,
        )
        logging.debug("Current URL before booking click: %s", page.url)
        save_screenshot(page, "10_before_booking_click")

        # ── Step 1: Click "Start New Booking" / "Book now" ──────────────
        logging.debug("Attempting to click booking CTA button")
        try:
            page.get_by_role("button", name=_START_BOOKING_RE).click(timeout=10_000)
            logging.debug("Clicked booking CTA via role+name selector")
        except Exception as exc:
            logging.warning(
                "Primary booking CTA selector failed (%s) — trying fallbacks", exc
            )
            save_screenshot(page, "10b_booking_cta_fallback")
            # Fallback 1: prominent action buttons
            try:
                page.locator("a.btn-primary, button.btn-primary").first.click(timeout=5_000)
                logging.debug("Clicked booking CTA via .btn-primary fallback")
            except Exception as exc2:
                logging.warning("Fallback 1 failed (%s) — trying link text", exc2)
                # Fallback 2: any link/button with booking-related text
                page.get_by_text(
                    re.compile(r"Book|Reserv|Agend", re.IGNORECASE)
                ).first.click(timeout=5_000)
                logging.debug("Clicked booking CTA via text-content fallback")

        logging.debug("Post-click URL: %s", page.url)
        save_screenshot(page, "11_after_booking_click")

        # Give the booking form time to load
        page.wait_for_load_state("networkidle", timeout=15_000)
        logging.debug("Booking form loaded — URL: %s", page.url)
        save_screenshot(page, "12_booking_form_loaded")

        # ── Step 2: Select Visa Centre ───────────────────────────────────
        logging.debug("Selecting Visa Centre: '%s'", visa_center)
        self._select_dropdown_option(page, 0, visa_center, "visa_center")
        save_screenshot(page, "13_after_visa_center")

        # ── Step 3: Select Visa Category ────────────────────────────────
        logging.debug("Selecting Visa Category: '%s'", visa_category)
        self._select_dropdown_option(page, 1, visa_category, "visa_category")
        save_screenshot(page, "14_after_visa_category")

        # ── Step 4: Select Visa Sub-Category ────────────────────────────
        logging.debug("Selecting Visa Sub-Category: '%s'", visa_sub_category)
        self._select_dropdown_option(page, 2, visa_sub_category, "visa_sub_category")
        save_screenshot(page, "15_after_visa_sub_category")

        # ── Step 5: Wait for and extract available dates ─────────────────
        logging.debug("Waiting for date availability response …")
        return self._extract_available_dates(page)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _select_dropdown_option(
        self, page: Page, index: int, value: str, label: str
    ) -> None:
        """Select an option from the nth Angular Material dropdown.

        Tries ``mat-form-field`` → ``select`` → ``ng-select`` in order.

        Args:
            page: The Playwright page object.
            index: Zero-based index of the dropdown on the page.
            value: The visible option text to select.
            label: Human-readable name used in log messages.
        """
        logging.debug("_select_dropdown_option: index=%d label=%s value='%s'", index, label, value)

        # Strategy A: Angular Material mat-form-field / mat-option
        try:
            fields = page.query_selector_all("mat-form-field")
            logging.debug("Found %d mat-form-field elements", len(fields))
            if index < len(fields):
                fields[index].click()
                page.wait_for_selector(
                    f'mat-option:has-text("{value}")', timeout=8_000
                ).click()
                logging.debug("Selected '%s' via mat-form-field[%d]", value, index)
                return
        except Exception as exc:
            logging.warning(
                "mat-form-field strategy failed for %s (index=%d): %s", label, index, exc
            )

        # Strategy B: native <select> element
        try:
            selects = page.query_selector_all("select")
            logging.debug("Found %d <select> elements", len(selects))
            if index < len(selects):
                selects[index].select_option(label=value)
                logging.debug("Selected '%s' via <select>[%d]", value, index)
                return
        except Exception as exc:
            logging.warning(
                "<select> strategy failed for %s (index=%d): %s", label, index, exc
            )

        # Strategy C: ng-select (common in newer Angular apps)
        try:
            ng_selects = page.query_selector_all("ng-select")
            logging.debug("Found %d ng-select elements", len(ng_selects))
            if index < len(ng_selects):
                ng_selects[index].click()
                page.wait_for_selector(
                    f'.ng-option:has-text("{value}")', timeout=8_000
                ).click()
                logging.debug("Selected '%s' via ng-select[%d]", value, index)
                return
        except Exception as exc:
            logging.warning(
                "ng-select strategy failed for %s (index=%d): %s", label, index, exc
            )

        logging.error(
            "All dropdown strategies exhausted for %s='%s' at index %d — "
            "check the screenshot to inspect actual DOM",
            label, value, index,
        )

    def _extract_available_dates(self, page: Page) -> Optional[List[str]]:
        """Wait for and extract appointment date strings from the page.

        Tries multiple known VFS patterns for displaying availability:
        - ``div.alert`` messages (older platform)
        - ``span.appointment-date`` / ``.available-date`` (newer platform)
        - Any element containing a date-like string as fallback

        Args:
            page: The Playwright page object.

        Returns:
            A list of date strings, or ``None`` if none found.
        """
        logging.debug("_extract_available_dates: waiting for availability response")

        # Give the page time to show a result after the last dropdown selection
        page.wait_for_timeout(3_000)
        save_screenshot(page, "16_waiting_for_dates")

        appointment_dates: List[str] = []

        # Pattern A: div.alert (older VFS Angular platform)
        try:
            page.wait_for_selector("div.alert", timeout=10_000)
            for element in page.query_selector_all("div.alert"):
                text = element.text_content() or ""
                logging.debug("div.alert text: %s", text.strip())
                date = extract_date_from_string(text)
                if date:
                    appointment_dates.append(date)
            if appointment_dates:
                logging.debug("Dates found via div.alert: %s", appointment_dates)
                return appointment_dates
        except Exception as exc:
            logging.debug("div.alert pattern not found: %s", exc)

        # Pattern B: elements with date-related class names (newer platform)
        for selector in [
            ".appointment-date",
            ".available-date",
            ".slot-date",
            "td.available",
            "div.available",
        ]:
            try:
                elements = page.query_selector_all(selector)
                if elements:
                    logging.debug("Found %d elements for selector '%s'", len(elements), selector)
                    for el in elements:
                        text = el.text_content() or ""
                        logging.debug("  text: %s", text.strip())
                        date = extract_date_from_string(text)
                        if date:
                            appointment_dates.append(date)
                    if appointment_dates:
                        logging.debug("Dates found via '%s': %s", selector, appointment_dates)
                        return appointment_dates
            except Exception as exc:
                logging.debug("Selector '%s' failed: %s", selector, exc)

        # Pattern C: scan the full page body for date patterns
        logging.debug("Trying full-page date scan as last resort …")
        try:
            body_text = page.locator("body").inner_text()
            logging.debug("Body text length: %d chars", len(body_text))
            # Look for lines containing date-like content
            for line in body_text.splitlines():
                date = extract_date_from_string(line)
                if date and date not in appointment_dates:
                    logging.debug("Date found in body scan: %s (from line: %s)", date, line.strip())
                    appointment_dates.append(date)
            if appointment_dates:
                return appointment_dates
        except Exception as exc:
            logging.debug("Full-page scan failed: %s", exc)

        save_screenshot(page, "17_no_dates_found")
        logging.info("No appointment dates could be extracted from the page.")
        return None
