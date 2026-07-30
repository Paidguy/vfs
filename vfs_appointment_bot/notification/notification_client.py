from abc import ABC, abstractmethod
from typing import List

from vfs_appointment_bot.utils.config_reader import get_config_section


class NotificationClient(ABC):
    """Abstract base class for notification clients.

    This class defines the common interface for notification clients used
    throughout the application. Subclasses must implement the
    :meth:`send_notification` method to provide channel-specific logic.
    """

    def __init__(self, config_section: str, required_config_keys: List[str]) -> None:
        """Initialise the client with configuration data.

        Args:
            config_section: The name of the INI configuration section
                containing client-specific settings.
            required_config_keys: Keys that *must* be present (and non-empty)
                in the configuration section.

        Raises:
            NotificationClientConfigValidationError: If any required key is
                missing or has an empty value.
        """
        self.required_keys = required_config_keys
        self.config = get_config_section(config_section)
        self._validate_config(required_config_keys)

    @abstractmethod
    def send_notification(self, message: str) -> None:
        """Send a notification message to the recipient.

        This method is abstract and must be implemented by subclasses to
        provide the specific logic for sending notifications through their
        respective channels.

        Args:
            message: The message content to be sent.
        """

    def _validate_config(self, required_config_keys: List[str]) -> None:
        """Validate that all required configuration keys exist and are non-empty.

        Args:
            required_config_keys: Keys that must be present in the section.

        Raises:
            NotificationClientConfigValidationError: On validation failure.
        """
        # Bug fix: required_config_keys is a list, not a set — convert both sides
        # before using the set-difference operator.
        missing_keys = set(required_config_keys) - set(self.config.keys())
        if missing_keys:
            raise NotificationClientConfigValidationError(
                f"Missing required configuration keys: {', '.join(sorted(missing_keys))}"
            )

        for key in self.required_keys:
            if not self.config.get(key):
                raise NotificationClientConfigValidationError(
                    f"Value for key '{key}' cannot be empty."
                )


class NotificationClientConfigValidationError(Exception):
    """Raised when notification client configuration validation fails."""


class NotificationClientError(Exception):
    """Raised when an error occurs during notification sending."""
