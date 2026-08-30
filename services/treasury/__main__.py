"""Allow `python3 -m services.treasury <cmd>` (typer app)."""

from services.treasury.cli import app

if __name__ == "__main__":
    app()
