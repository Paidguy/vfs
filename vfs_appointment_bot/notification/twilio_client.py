import logging
from typing import Optional

from twilio.rest import Client

from vfs_appointment_bot.notification.notification_client import NotificationClient
from vfs_appointment_bot.utils.config_reader import get_config_bool


class TwilioClient(NotificationClient):
    """Concrete implementation of NotificationClient for the Twilio channel.

    This class sends notifications via Twilio SMS and optionally initiates a
    voice call. It inherits from :class:`NotificationClient` and implements
    :meth:`send_notification` for Twilio-specific logic.
    """

    def __init__(self) -> None:
        """Initialise the Twilio client.

        Reads Twilio credentials and phone numbers from the ``[twilio]`` INI
        section and validates that all required keys are present.
        """
        required_config_keys = [
            "to_num",
            "from_num",
            "account_sid",
            "auth_token",
        ]
        super().__init__("twilio", required_config_keys)

    def send_notification(self, message: str) -> None:
        """Send a notification via Twilio SMS, and optionally a voice call.

        The ``call_enabled`` INI key controls whether a call is also placed.
        ``sms_enabled`` defaults to ``True``; set it to ``False`` to suppress
        the SMS (voice-only mode).

        Args:
            message: The message content to send as an SMS body.
        """
        auth_token: str = self.config.get("auth_token")
        account_sid: str = self.config.get("account_sid")
        to_num: str = self.config.get("to_num")
        from_num: str = self.config.get("from_num")
        url: Optional[str] = self.config.get("url")

        # Bug fix: config values from INI are always strings; use get_config_bool
        # so "False" is not treated as truthy by a plain `if` check.
        sms_enabled: bool = get_config_bool("twilio", "sms_enabled", default=True)
        call_enabled: bool = get_config_bool("twilio", "call_enabled", default=False)

        if sms_enabled:
            self._send_message(message, auth_token, account_sid, to_num, from_num)

        if call_enabled:
            self._call(url, auth_token, account_sid, to_num, from_num)

    def _send_message(
        self,
        message: str,
        auth_token: str,
        account_sid: str,
        to_num: str,
        from_num: str,
    ) -> None:
        """Send an SMS via the Twilio REST API.

        Args:
            message: The SMS body text.
            auth_token: Twilio account authentication token.
            account_sid: Twilio account SID.
            to_num: Recipient phone number (E.164 format).
            from_num: Twilio sender phone number (E.164 format).
        """
        client = Client(account_sid, auth_token)
        client.messages.create(to=to_num, from_=from_num, body=message)
        logging.info("Twilio SMS sent successfully!")

    def _call(
        self,
        url: Optional[str],
        auth_token: str,
        account_sid: str,
        to_num: str,
        from_num: str,
    ) -> None:
        """Initiate a Twilio voice call (if a TwiML URL is configured).

        Args:
            url: TwiML URL for the call content. If ``None`` or empty, the
                call is skipped and a warning is logged.
            auth_token: Twilio account authentication token.
            account_sid: Twilio account SID.
            to_num: Recipient phone number (E.164 format).
            from_num: Twilio sender phone number (E.164 format).
        """
        if url:
            client = Client(account_sid, auth_token)
            client.calls.create(from_=from_num, to=to_num, url=url)
            logging.info("Twilio call request sent successfully!")
        else:
            logging.warning(
                "call_enabled is True but no TwiML URL is configured — skipping call."
            )
