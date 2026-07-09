"""Kokonut Intelligence Prefect workflow definitions.

Each flow wraps an existing CLI tool as a Prefect flow.
Flows are scheduled via Prefect UI or deployment YAML.
"""

from prefect import flow, task
