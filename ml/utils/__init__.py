"""
Utilities

Database and helper functions:
- MLDatabase: Database operations for predictions and scores
- get_ml_database: Get singleton database instance
"""

from ml.utils.database import (
    MLDatabase,
    get_ml_database,
)

__all__ = [
    "MLDatabase",
    "get_ml_database",
]
