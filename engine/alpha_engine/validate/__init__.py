"""Data validation: the checks a careful analyst runs on any business export before trusting a number."""
from .checks import validate, CHECKS

__all__ = ["validate", "CHECKS"]
