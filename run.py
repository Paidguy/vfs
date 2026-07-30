"""Root-level launcher for vfs-appointment-bot.

Run this script from the repo root (``~/vfs/``) so that the
``vfs_appointment_bot`` package is on ``sys.path`` automatically —
no ``pip install`` or ``PYTHONPATH`` tweaking required.

Usage (from ~/vfs/):
    python run.py -sc ao -dc pt
    python run.py -sc ao -dc pt -ap "visa_center=Angola – Luanda,visa_category=Nacional,visa_sub_category=Nacional"
"""

import os
import sys

# Insert the repo root (directory of this file) at the front of sys.path so
# that ``import vfs_appointment_bot`` resolves without an editable install.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vfs_appointment_bot.main import main  # noqa: E402

if __name__ == "__main__":
    main()
