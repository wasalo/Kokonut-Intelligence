"""Export CLI — delegates to report_generator for report generation and exports."""

from __future__ import annotations

import sys

from .report_generator import main


def _entry() -> None:
    """Wrapper so mount_argparse can resolve services.export.cli.main."""
    main()


if __name__ == "__main__":
    _entry()
