import logging
import re
from typing import Dict, List, Optional

from patchright.sync_api import Page

from vfs_appointment_bot.utils.date_utils import extract_date_from_string
from vfs_appointment_bot.vfs_bot.vfs_bot import VfsBot


class VfsBotIt(VfsBot):
    """VFS bot implementation for Italy (IT) as destination country.

    Handles login, cookie-consent dismissal, and appointment checking for
    the VFS Global Italy portal (``visa.vfsglobal.com/.../ita/...``).

    Supports both standard applicants and Morocco (MA) applicants who have
    an additional "Payment Mode" dropdown on the booking form.
    """

    def __init__(self, source_country_code: str) -> None:
        """Initialise VfsBotIt.

        Args:
            source_country_code: ISO 3166-1 alpha-2 code of the applicant's
                country. When ``"MA"`` (Morocco), an extra ``"payment_mode"``
                parameter is required on the booking form.
        """
        super().__init__()
        self.source_country_code = source_country_code
        self.destination_country_code = "IT"
        self.appointment_param_keys = [
            "visa_center",
            "visa_category",
            "visa_sub_category",
        ]
        if self.source_country_code == "MA":
            self.appointment_param_keys.append("payment_mode")

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
        """Log in to the Italy VFS portal.

        Uses semantic locators (ARIA label / regex) rather than the fragile
        ``#mat-input-N`` auto-generated IDs which change every Angular
        bootstrap.

        Args:
            page: The Playwright page object.
            email_id: VFS account email address.
            password: VFS account password.

        Raises:
            Exception: If the post-login ``"Start New Booking"`` button is
                not found within the default timeout.
        """
        email_input = page.get_by_label(re.compile(r"email", re.IGNORECASE))
        password_input = page.get_by_label(re.compile(r"^password\*?$", re.IGNORECASE))

        email_input.fill(email_id)
        password_input.fill(password)

        page.get_by_role("button", name=re.compile(r"sign in", re.IGNORECASE)).click()

        # Confirm successful login by waiting for the dashboard button.
        page.get_by_role(
            "button", name=self._START_BOOKING_RE
        ).wait_for(state="visible")

    def check_for_appointment(
        self, page: Page, appointment_params: Dict[str, str]
    ) -> Optional[List[str]]:
        """Navigate the IT booking form and extract available appointment dates.

        Clicks "Start New Booking", selects the visa centre / category /
        sub-category from the Angular Material dropdowns, and — for Morocco
        applicants — selects the payment mode as well.

        Args:
            page: The Playwright page object.
            appointment_params: Must contain ``"visa_center"``,
                ``"visa_category"``, ``"visa_sub_category"``, and
                ``"payment_mode"`` (Morocco only).

        Returns:
            A list of date strings if slots are available, or ``None``.
        """
        page.get_by_role("button", name=self._START_BOOKING_RE).click()

        # Select Visa Centre (first mat-form-field on the page)
        page.wait_for_selector("mat-form-field").click()
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

        # Morocco applicants have an extra Payment Mode dropdown
        if self.source_country_code == "MA":
            page.query_selector_all("mat-form-field")[3].click()
            page.wait_for_selector(
                f'mat-option:has-text("{appointment_params.get("payment_mode")}")'
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
