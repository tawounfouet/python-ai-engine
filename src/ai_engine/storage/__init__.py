"""
AI Engine — Storage Layer.

Persistence abstraite avec plusieurs implémentations concrètes.

Usage:
    from ai_engine.storage import InMemoryStorage, SQLiteStorage, StorageBackend

    # Pour les tests / prototypage :
    storage = InMemoryStorage()

    # Pour les scripts / CLI :
    storage = SQLiteStorage("my_project.db")

    # Pour typer une dépendance :
    def my_service(storage: StorageBackend): ...
"""

from ai_engine.storage.base import StorageBackend
from ai_engine.storage.memory import InMemoryStorage
from ai_engine.storage.sqlite import SQLiteStorage

__all__ = [
    "InMemoryStorage",
    "SQLiteStorage",
    "StorageBackend",
]
