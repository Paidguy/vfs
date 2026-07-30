import os
from configparser import ConfigParser
from typing import Dict, Optional

_config: Optional[ConfigParser] = None


def initialize_config(config_dir: str = "config") -> None:
    """Read all INI configuration files in ``config_dir`` and cache the result.

    Also reads a user-supplied config file from the ``VFS_BOT_CONFIG_PATH``
    environment variable (if set), which takes precedence over the bundled files.

    Args:
        config_dir: Directory containing ``*.ini`` configuration files.
                    Defaults to ``"config"``.
    """
    global _config
    if not _config:
        _config = ConfigParser()
        if os.path.isdir(config_dir):
            for entry in os.scandir(config_dir):
                if entry.is_file() and entry.name.endswith(".ini"):
                    config_file_path = os.path.join(config_dir, entry.name)
                    _config.read(config_file_path)

    # User-defined config file overrides bundled defaults.
    user_config_path = os.environ.get("VFS_BOT_CONFIG_PATH")
    if user_config_path:
        _config.read(user_config_path)


def get_config_section(section: str, default: Optional[Dict] = None) -> Dict:
    """Return a configuration section as a plain dictionary.

    Args:
        section: The name of the INI section to retrieve.
        default: Fallback dictionary if the section does not exist.

    Returns:
        A dictionary of key-value pairs for the section, or ``default`` (empty
        dict if not supplied) when the section is absent.
    """
    if _config and _config.has_section(section):
        return dict(_config[section])
    return default or {}


def get_config_value(
    section: str, key: str, default: Optional[str] = None
) -> Optional[str]:
    """Return a single configuration value.

    Args:
        section: The INI section name.
        key: The key within the section.
        default: Value to return when the section or key is not found.

    Returns:
        The string value, or ``default`` when absent.
    """
    if _config and _config.has_section(section) and _config.has_option(section, key):
        return _config[section][key]
    return default


def get_config_bool(
    section: str, key: str, default: bool = False
) -> bool:
    """Return a configuration value coerced to a boolean.

    Accepts ``"true"``, ``"1"``, ``"yes"`` (case-insensitive) as truthy values;
    everything else is falsy.

    Args:
        section: The INI section name.
        key: The key within the section.
        default: Value to return when the section or key is not found.

    Returns:
        The boolean interpretation of the config value, or ``default``.
    """
    value = get_config_value(section, key)
    if value is None:
        return default
    return value.strip().lower() in ("true", "1", "yes")
