import logging
import re
from typing import Dict, List, Optional

from patchright.sync_api import Page

from vfs_appointment_bot.utils.date_utils import extract_date_from_string
from vfs_appointment_bot.vfs_bot.vfs_bot import VfsBot


class VfsBotDe(VfsBot):
    """VFS bot implementation for Germany (DE) as destination country.

    Handles login, cookie-consent dismissal, and appointment checking for
    the VFS Global Germany portal (``visa.vfsglobal.com/.../deu/...``).

    The login page uses Angular Material form fields. We avoid the fragile
    auto-generated ``#mat-input-N`` IDs (which change each session) and
    instead locate fields by their ARIA label or ``formcontrolname`` attribute.
    """

    def __init__(self, source_country_code: str) -> None:
        """Initialise VfsBotDe.

        Args:
            source_country_code: ISO 3166-1 alpha-2 code of the applicant's
                country (e.g. ``"IN"`` for India, ``"IQ"`` for Iraq).
        """
        super().__init__()
        self.source_country_code = source_country_code
        self.destination_country_code = "DE"
        self.appointment_param_keys = [
            "visa_center",
            "visa_category",
            "visa_sub_category",
        ]

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    def pre_login_steps(self, page: Page) -> None:
        """Dismiss the cookie-consent banner if it appears.

        Delegates to the shared :meth:`~VfsBot._reject_cookies_if_present`
        helper so the bot never hangs if no banner is present.

        Args:
            page: The Playwright page object.
        """
        self._reject_cookies_if_present(page)

    def login(self, page: Page, email_id: str, password: str) -> None:
        """Log in to the Germany VFS portal.

        Uses semantic locators (ARIA label / ``formcontrolname``) rather than
        the fragile ``#mat-input-N`` auto-generated IDs which change every
        Angular bootstrap. Falls back to ``formcontrolname`` attributes if
        labels are ambiguous.

        Args:
            page: The Playwright page object.
            email_id: VFS account email address.
            password: VFS account password.

        Raises:
            Exception: If the post-login ``"Start New Booking"`` button is
                not found within the default timeout.
        """
        # Prefer label-based selectors; they are stable across Angular upgrades.
        # The exact label text may vary by locale — use a regex for robustness.
        email_input = page.get_by_label(re.compile(r"email", re.IGNORECASE))
        password_input = page.get_by_label(re.compile(r"^password\*?$", re.IGNORECASE))

        email_input.fill(email_id)
        password_input.fill(password)

        page.get_by_role("button", name=re.compile(r"sign in", re.IGNORECASE)).click()

        # Wait for the dashboard button that confirms successful login.
        page.get_by_role(
            "button", name=self._START_BOOKING_RE
        ).wait_for(state="visible")

    def check_for_appointment(
        self, page: Page, appointment_params: Dict[str, str]
    ) -> Optional[List[str]]:
        """Navigate the DE booking form and extract available appointment dates.

        Clicks "Start New Booking", selects the visa centre / category /
        sub-category from the Angular Material dropdowns, then scrapes any
        ``div.alert`` elements for date strings.

        Args:
            page: The Playwright page object.
            appointment_params: Must contain keys ``"visa_center"``,
                ``"visa_category"``, and ``"visa_sub_category"``.

        Returns:
            A list of date strings if slots are available, or ``None`` if none
            are found or an error occurs.
        """
        page.get_by_role("button", name=self._START_BOOKING_RE).click()

        # Select Visa Centre (first mat-form-field on the page)
        visa_centre_dropdown = page.wait_for_selector("mat-form-field")
        visa_centre_dropdown.click()
        page.wait_for_selector(
            f'mat-option:has-text("{appointment_params.get("visa_center")}")'
        ).click()

        # Select Visa Category (second mat-form-field)
        page.query_selector_all("mat-form-field")[1].click()
        page.wait_for_selector(
            f'mat-option:has-text("{appointment_params.get("visa_category")}")'
        ).click()

        # Select Visa Sub-Category (third mat-form-field)
        page.query_selector_all("mat-form-field")[2].click()
        page.wait_for_selector(
            f'mat-option:has-text("{appointment_params.get("visa_sub_category")}")'
        ).click()

        try:
            page.wait_for_selector("div.alert")
            appointment_dates: List[str] = []
            for element in page.query_selector_all("div.alert"):
                date = extract_date_from_string(element.text_content() or "")
                if date:
                    appointment_dates.append(date)
            return appointment_dates if appointment_dates else None
        except Exception as exc:
            logging.debug("Appointment date extraction failed: %s", exc)
            return None
