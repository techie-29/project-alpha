"""Cell-level cleaning that works on any table, whatever its columns mean.

It runs right after a file is read and before the engine builds on it. It finds problems cell by cell (missing, text where a
number belongs, impossible or negative values, dates that cannot be real, bad emails, repeated rows, inconsistent spelling,
extreme values), fixes the safe ones on its own (and says so), and applies the owner's choice for the rest."""
from .scan import run, TYPES, DEFAULT_CHOICE

__all__ = ["run", "TYPES", "DEFAULT_CHOICE"]
