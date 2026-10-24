"""Entry point so the tool can be run with `python -m instaselftool`."""

import sys

from .cli import run

if __name__ == "__main__":
    sys.exit(run())
