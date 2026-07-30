import argparse
import logging
import sys
from importlib.metadata import version, PackageNotFoundError
from typing import Dict

from vfs_appointment_bot.utils.config_reader import get_config_value, initialize_config
from vfs_appointment_bot.utils.timer import countdown
from vfs_appointment_bot.vfs_bot.vfs_bot import LoginError
from vfs_appointment_bot.vfs_bot.vfs_bot_factory import (
    UnsupportedCountryError,
    get_vfs_bot,
)


def _get_version() -> str:
    """Return the installed package version, or ``"unknown"`` if unavailable."""
    try:
        return version("vfs-appointment-bot")
    except PackageNotFoundError:
        return "unknown"


class KeyValueAction(argparse.Action):
    """Custom argparse action that parses ``key=value,key=value`` strings.

    Used by the ``--appointment-params`` argument to collect booking filters
    (visa centre, category, sub-category, etc.) from the command line without
    requiring an interactive prompt.

    Format: ``key1=value1,key2=value2,...``
    """

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str,
        option_string: str = None,
    ) -> None:
        try:
            appointment_params: Dict[str, str] = {
                key.strip(): value.strip()
                for key, value in (item.split("=", 1) for item in values.split(","))
            }
            setattr(namespace, "appointment_params", appointment_params)
        except ValueError:
            parser.error(
                f"Invalid value format for {option_string}. "
                "Expected comma-separated key=value pairs, e.g. "
                "visa_center=Berlin,visa_category=National Visa"
            )


def main() -> None:
    """Entry point for the VFS Appointment Bot.

    Sets up logging, reads configuration, parses CLI arguments, and runs the
    VFS appointment-checking loop until a slot is found or an unrecoverable
    error occurs.
    """
    _initialize_logger()
    initialize_config()

    parser = argparse.ArgumentParser(
        prog="vfs-appointment-bot",
        description=(
            "VFS Appointment Bot — automatically checks the VFS Global portal "
            "for available visa appointment slots and notifies you when one opens up."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    required_args = parser.add_argument_group("required arguments")
    required_args.add_argument(
        "-sc",
        "--source-country-code",
        type=str,
        help="ISO 3166-1 alpha-2 country code you are applying *from* (e.g. IN, AO)",
        metavar="<country_code>",
        required=True,
    )
    required_args.add_argument(
        "-dc",
        "--destination-country-code",
        type=str,
        help="ISO 3166-1 alpha-2 country code of the embassy/VFS (e.g. DE, IT, PT)",
        metavar="<country_code>",
        required=True,
    )
    parser.add_argument(
        "-ap",
        "--appointment-params",
        type=str,
        default=None,
        help=(
            "Comma-separated key=value pairs for booking filters "
            "(e.g. visa_center=Berlin,visa_category=National Visa). "
            "Omit to be prompted interactively."
        ),
        action=KeyValueAction,
        metavar="<key1=value1,key2=value2,...>",
    )

    args = parser.parse_args()
    source_country_code = args.source_country_code
    destination_country_code = args.destination_country_code

    try:
        while True:
            vfs_bot = get_vfs_bot(source_country_code, destination_country_code)
            appointment_found = vfs_bot.run(args)
            if appointment_found:
                break
            countdown(
                int(get_config_value("default", "interval", "180")),
                "Next appointment check in",
            )
    except (UnsupportedCountryError, LoginError) as exc:
        logging.error(exc)
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
        sys.exit(0)
    except Exception as exc:
        logging.exception("Unexpected error: %s", exc)
        sys.exit(1)


def _initialize_logger() -> None:
    """Configure the root logger with file and console handlers.

    - File handler (``app.log``): full ``%(levelname)s`` and source location.
    - Stream handler (``stdout``): concise timestamp + message for the terminal.

    Safe to call multiple times — handlers are not duplicated because
    ``basicConfig`` is a no-op when handlers are already attached.
    """
    # Avoid adding duplicate handlers on repeated calls (e.g. in tests).
    root = logging.getLogger()
    if root.handlers:
        return

    file_handler = logging.FileHandler("app.log", mode="a", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] %(message)s"
        )
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, stream_handler],
    )


if __name__ == "__main__":
    main()
