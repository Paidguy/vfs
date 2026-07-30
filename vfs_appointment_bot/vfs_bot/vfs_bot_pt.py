import logging
import re
from typing import Dict, List, Optional

from patchright.sync_api import Page

from vfs_appointment_bot.utils.date_utils import extract_date_from_string
from vfs_appointment_bot.vfs_bot.vfs_bot import VfsBot

# ── Label / button text constants ─────────────────────────────────────────────
# Confirmed from live screenshots of visa.vfsglobal.com/ago/en/prt/login.
# The Sign In button is labelled "Sign In" in the English locale. The Portuguese
# locale path (/ago/pt/prt/) may render "Iniciar Sessão" — the regex covers both.
_SIGN_IN_RE = re.compile(r"Sign In|Iniciar Sess[aã]o", re.IGNORECASE)

# NOT YET CONFIRMED: exact text of the post-login booking trigger button.
# The pre-login landing page uses "Book now"; post-login behaviour is unverified
# because the AO-PT portal (footer "AR-8.0.28") is a newer VFS platform version
# with a redesigned booking flow. Update once the real post-login DOM is inspected.
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
        site. The **check_for_appointment** step is a *best-effort estimate*
        that mirrors the Angular-based booking form used by the Germany/Italy
        bots. The AO-PT site runs a newer VFS platform version ("AR-8.0.28")
        with a visibly different UI; this part has **not** been verified
        against the live booking form and may need adjustment.
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
        try:
            page.get_by_role(
                "button",
                name=re.compile(r"Reject All|Rejeitar", re.IGNORECASE),
            ).click(timeout=3_000)
            logging.debug("Rejected cookie consent banner.")
        except Exception:
            pass

    def login(self, page: Page, email_id: str, password: str) -> None:
        """Log in to the Angola→Portugal VFS portal.

        Confirmed against live screenshots:
        - Email field: placeholder ``"jane.doe@email.com"``
        - Password field: labelled ``"Password"`` (not "Confirm Password",
          which only appears on the registration page)
        - Submit button: labelled ``"Sign In"``
        - A Cloudflare Turnstile widget must auto-resolve to "Success" before
          the Sign In button becomes clickable. We give it a 5-second grace
          period. This is a best-effort wait; manual CAPTCHA challenges are
          not supported (see README known issues).

        Args:
            page: The Playwright page object.
            email_id: VFS account email address.
            password: VFS account password.

        Raises:
            Exception: If the page URL does not change away from ``/login``
                within 30 seconds, indicating a failed login.
        """
        page.get_by_placeholder("jane.doe@email.com").fill(email_id)
        page.get_by_label(
            re.compile(r"^Password\*?$"), exact=False
        ).fill(password)

        # Allow Cloudflare Turnstile time to auto-resolve before clicking.
        page.wait_for_timeout(5_000)

        page.get_by_role("button", name=_SIGN_IN_RE).click()

        # Use URL change as a proxy for successful login.
        # TODO: Replace with a real post-login element once the dashboard
        # DOM has been inspected on the live site.
        page.wait_for_function(
            "() => !window.location.pathname.endsWith('/login')",
            timeout=30_000,
        )

    def check_for_appointment(
        self, page: Page, appointment_params: Dict[str, str]
    ) -> Optional[List[str]]:
        """Navigate the PT booking form and extract available dates.

        .. warning::
            This implementation is **unverified** for the AO-PT platform
            (newer VFS "AR-8.0.28" version). It mirrors the Angular
            ``mat-form-field`` / ``mat-option`` / ``div.alert`` pattern used
            by the Germany and Italy bots as a starting point. Adjust
            selectors once the live booking form has been inspected.

        Args:
            page: The Playwright page object.
            appointment_params: Must contain ``"visa_center"``,
                ``"visa_category"``, and ``"visa_sub_category"``.

        Returns:
            A list of date strings if slots are available, or ``None``.
        """
        page.get_by_role("button", name=_START_BOOKING_RE).click()

        # Select Visa Centre (first mat-form-field — UNVERIFIED for AO-PT)
        page.wait_for_selector("mat-form-field").click()
        page.wait_for_selector(
            f'mat-option:has-text("{appointment_params.get("visa_center")}")'
        ).click()

        # Select Visa Category (second mat-form-field — UNVERIFIED)
        page.query_selector_all("mat-form-field")[1].click()
        page.wait_for_selector(
            f'mat-option:has-text("{appointment_params.get("visa_category")}")'
        ).click()

        # Select Visa Sub-Category (third mat-form-field — UNVERIFIED)
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
