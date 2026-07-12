"""Cron expression parser for the task scheduler.

Parses standard 5-field cron expressions and computes next run times.
Supports: minute, hour, day-of-month, month, day-of-week.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Optional


def parse_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    """Parse a single cron field into a set of valid values."""
    values = set()

    for part in field.split(","):
        part = part.strip()

        if part == "*":
            values.update(range(min_val, max_val + 1))
        elif "-" in part:
            start, end = part.split("-", 1)
            values.update(range(int(start), int(end) + 1))
        elif "/" in part:
            base, step = part.split("/", 1)
            if base == "*":
                start = min_val
            else:
                start = int(base)
            step = int(step)
            values.update(range(start, max_val + 1, step))
        else:
            values.add(int(part))

    return {v for v in values if min_val <= v <= max_val}


def parse_cron(expression: str) -> dict:
    """Parse a 5-field cron expression into component sets.

    Returns dict with keys: minute, hour, day, month, weekday
    """
    fields = expression.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression: {expression!r} (expected 5 fields)")

    return {
        "minute": parse_cron_field(fields[0], 0, 59),
        "hour": parse_cron_field(fields[1], 0, 23),
        "day": parse_cron_field(fields[2], 1, 31),
        "month": parse_cron_field(fields[3], 1, 12),
        "weekday": parse_cron_field(fields[4], 0, 6),  # 0=Sunday
    }


def next_run_time(
    expression: str,
    after: Optional[datetime] = None,
    max_lookahead_days: int = 7,
) -> datetime:
    """Compute the next run time after a given datetime.

    Args:
        expression: Standard 5-field cron expression
        after: Compute next run after this time (default: now)
        max_lookahead_days: Maximum days to look ahead

    Returns:
        Next datetime when the cron should fire
    """
    if after is None:
        after = datetime.now(timezone.utc)

    parsed = parse_cron(expression)
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

    end = after + timedelta(days=max_lookahead_days)

    while candidate < end:
        if (
            candidate.minute in parsed["minute"]
            and candidate.hour in parsed["hour"]
            and candidate.day in parsed["day"]
            and candidate.month in parsed["month"]
            and candidate.weekday() in parsed["weekday"]
        ):
            return candidate
        candidate += timedelta(minutes=1)

    raise RuntimeError(
        f"No matching time found within {max_lookahead_days} days "
        f"for cron: {expression!r}"
    )


def describe_cron(expression: str) -> str:
    """Human-readable description of a cron expression."""
    parsed = parse_cron(expression)
    parts = []

    if len(parsed["minute"]) == 1:
        parts.append(f"at minute {min(parsed['minute'])}")
    elif parsed["minute"] == set(range(0, 60)):
        parts.append("every minute")
    else:
        parts.append(f"at minutes {sorted(parsed['minute'])}")

    if len(parsed["hour"]) == 1:
        parts.append(f"at hour {min(parsed['hour'])}")
    elif parsed["hour"] == set(range(0, 24)):
        parts.append("every hour")
    else:
        parts.append(f"at hours {sorted(parsed['hour'])}")

    if len(parsed["month"]) < 12:
        parts.append(f"in months {sorted(parsed['month'])}")

    return " ".join(parts)
