"""Metric + AI brain: the engine's metric catalogue and order-form calculator, with the AI choosing what to look into."""
from .brain import analyse, ask, make_investigator, baseline_cards

__all__ = ["analyse", "ask", "make_investigator", "baseline_cards"]
