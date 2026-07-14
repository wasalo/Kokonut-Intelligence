"""Management domain constants and spec-derived helpers."""

WORK_ITEM_STATUSES = ("draft", "assigned", "in_progress", "blocked", "done", "cancelled")
WORK_ITEM_PRIORITIES = ("low", "medium", "high", "critical")
PARTY_TYPES = ("staff", "farmer", "agent", "team")
RACI_ROLES = ("accountable", "responsible", "consulted", "informed")
ACTOR_TYPES = ("staff", "farmer", "agent", "system")

TERMINAL_STATES = {"done", "cancelled"}
