import argparse
import logging
import sys
from datetime import datetime
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from typing import Dict

from vfs_appointment_bot.utils.config_reader import get_config_value, initialize_config
from vfs_appointment_bot.utils.timer import countdown
from vfs_appointment_bot.vfs_bot.vfs_bot import LoginError
from vfs_appointment_bot.vfs_bot.vfs_bot_factory import (
    UnsupportedCountryError,
    get_vfs_bot,
)

# Repo root is two levels up from this file:
# <repo_root>/vfs_appointment_bot/main.py
_REPO_ROOT = Path(__file__).resolve().parent.parent


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
    # Logging is initialised first so that every subsequent step is captured.
    log_file = _initialize_logger()
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

    logging.info("=" * 60)
    logging.info("VFS Appointment Bot v%s", _get_version())
    logging.info("Log file: %s", log_file)
    logging.info("Route: %s → %s", source_country_code.upper(), destination_country_code.upper())
    logging.info("=" * 60)

    try:
        while True:
            vfs_bot = get_vfs_bot(source_country_code, destination_country_code)
            appointment_found = vfs_bot.run(args)
            if appointment_found:
                logging.info("Appointment found — bot is stopping.")
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


def _initialize_logger() -> Path:
    """Configure the root logger with a timestamped file handler and a console handler.

    - **File handler** (``logs/vfs_bot_<timestamp>.log``): captures *everything*
      at ``DEBUG`` level — full source location, thread, etc.
    - **Stream handler** (``stdout``): also ``DEBUG`` level so every detail is
      visible in the terminal as well.

    The log directory is created next to the repo root automatically.

    Returns:
        The :class:`~pathlib.Path` to the log file that was opened.

    Notes:
        Safe to call multiple times — a no-op if handlers are already attached.
    """
    root = logging.getLogger()
    if root.handlers:
        # Already initialised (e.g. during tests) — return a dummy path.
        return Path("app.log")

    log_dir = _REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"vfs_bot_{timestamp}.log"

    detailed_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(detailed_fmt)
    file_handler.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(console_fmt)
    stream_handler.setLevel(logging.DEBUG)

    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    return log_file


if __name__ == "__main__":
    main()
