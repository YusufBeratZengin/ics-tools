"""Entry point for executing ics-tools via `python -m ics_tools`."""

import sys
from ics_tools.cli import main

if __name__ == "__main__":
    sys.exit(main())
