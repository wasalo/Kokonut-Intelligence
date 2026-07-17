"""Read-only PostgreSQL schema relationship inventory."""

from .inventory import build_inventory, inventory_as_markdown

__all__ = ["build_inventory", "inventory_as_markdown"]
