import logging
import smtplib

from vfs_appointment_bot.notification.notification_client import NotificationClient


class EmailClient(NotificationClient):
    """Concrete implementation of NotificationClient for Gmail SMTP.

    Sends notifications via a Gmail account using SMTP over SSL (port 465).
    Requires a Gmail *App Password* (not your regular password) — see
    https://support.google.com/accounts/answer/185833 for setup instructions.
    """

    def __init__(self) -> None:
        """Initialise the email client.

        Reads ``email`` and ``password`` from the ``[email]`` INI section and
        validates they are present.
        """
        required_keys = ["email", "password"]
        super().__init__("email", required_keys)

    def send_notification(self, message: str) -> None:
        """Send a notification email to the configured Gmail address.

        The email is sent from and to the same address (self-notification).

        Args:
            message: The body text of the email notification.

        Raises:
            smtplib.SMTPException: If the SMTP connection or send fails.
        """
        email: str = self.config.get("email")
        password: str = self.config.get("password")
        email_text = self._construct_email_text(email, message)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
            smtp_server.ehlo()
            smtp_server.login(email, password)
            smtp_server.sendmail(email, email, email_text)

        logging.info("Email notification sent successfully!")

    def _construct_email_text(self, email: str, message: str) -> str:
        """Build a minimal RFC-2822 compliant email text.

        Args:
            email: The sender/recipient address.
            message: The body content.

        Returns:
            A formatted string suitable for ``smtplib.sendmail``.
        """
        return (
            f"From: {email}\n"
            f"To: {email}\n"
            f"Subject: VFS Appointment Bot — Slot Found!\n\n"
            f"{message}"
        )
