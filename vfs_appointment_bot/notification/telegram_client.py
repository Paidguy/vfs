import logging

import requests

from vfs_appointment_bot.notification.notification_client import NotificationClient


class TelegramClient(NotificationClient):
    """Concrete implementation of NotificationClient for the Telegram channel.

    This class sends notifications through the Telegram Bot API. It inherits
    from :class:`NotificationClient` and implements :meth:`send_notification`
    for Telegram-specific logic.
    """

    def __init__(self) -> None:
        """Initialise the Telegram client.

        Reads ``bot_token``, ``chat_id``, and ``parse_mode`` from the
        ``[telegram]`` INI section and validates they are present.
        """
        required_keys = ["bot_token", "chat_id", "parse_mode"]
        super().__init__("telegram", required_keys)

    def send_notification(self, message: str) -> None:
        """Send a notification message via the Telegram Bot API.

        Constructs and sends a ``sendMessage`` GET request. Raises an
        exception if the API call fails.

        Args:
            message: The message content to send.

        Raises:
            requests.HTTPError: If the Telegram API returns an error status.
        """
        bot_token: str = self.config.get("bot_token")
        chat_id: str = self.config.get("chat_id")
        parse_mode: str = self.config.get("parse_mode")

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {
            "chat_id": chat_id,
            "parse_mode": parse_mode,
            "text": message,
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        logging.info("Telegram message sent successfully!")
