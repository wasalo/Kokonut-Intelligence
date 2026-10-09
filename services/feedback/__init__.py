"""Feedback controller — tracks outcomes and adapts the system.

Records action outcomes, evaluates their effectiveness, and generates
feedback loops that adjust thresholds, weights, and sampling rates.
Closes the Observe→Orient→Decide→Act→Observe loop.
"""

from .controller import FeedbackController
from .outcomes import ActionOutcomeTracker
from .automation import FeedbackAutomation

__all__ = ["FeedbackController", "ActionOutcomeTracker", "FeedbackAutomation"]
