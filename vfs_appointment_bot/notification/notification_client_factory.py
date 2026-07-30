from vfs_appointment_bot.notification.notification_client import NotificationClient


class UnsupportedNotificationChannelError(Exception):
    """Raised when an unsupported notification channel is provided."""


def get_notification_client(channel: str) -> NotificationClient:
    """Return the appropriate notification client for ``channel``.

    Supported channel names (case-insensitive, leading/trailing whitespace
    is stripped):

    - ``"email"``    — Gmail SMTP
    - ``"telegram"`` — Telegram Bot API
    - ``"twilio"``   — Twilio SMS / Voice Call

    Args:
        channel: The notification channel name as configured in ``config.ini``
            under ``[notification] channels``.

    Returns:
        An instantiated :class:`NotificationClient` subclass.

    Raises:
        UnsupportedNotificationChannelError: If the channel name is not
            recognised.
    """
    normalised = channel.strip().lower()

    if normalised == "telegram":
        from .telegram_client import TelegramClient

        return TelegramClient()
    elif normalised == "twilio":
        from .twilio_client import TwilioClient

        return TwilioClient()
    elif normalised == "email":
        from .email_client import EmailClient

        return EmailClient()
    else:
        raise UnsupportedNotificationChannelError(
            f"Notification channel '{channel}' is not supported. "
            "Supported channels: email, telegram, twilio."
        )
