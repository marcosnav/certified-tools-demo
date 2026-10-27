"""CODA certified tools: pre-vetted methods and queries for common questions."""

from .sales import (
    GlobalBranchesSanitizedSales,
    get_sql,
    global_branches_sanitized_sales,
)

__all__ = [
    "GlobalBranchesSanitizedSales",
    "global_branches_sanitized_sales",
    "get_sql",
]

__version__ = "1.1.0"
