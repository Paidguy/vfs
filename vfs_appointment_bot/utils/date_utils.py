import re
from typing import Optional


def extract_date_from_string(text: str) -> Optional[str]:
    """Extract the first date string found in ``text``.

    Supports three common date formats:
      - ``YYYY-MM-DD``  (ISO 8601)
      - ``DD-MM-YYYY``
      - ``DD-MM-YY``

    Args:
        text: The raw text to search for a date.

    Returns:
        The matched date string, or ``None`` if no date is found.
    """
    pattern = r"(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}-\d{2}-\d{2})"
    match = re.search(pattern, text)
    if match:
        return match.group()
    return None
