"""
This example illustrates a basic usage of the Container class to register
a concrete type by base type, and its activation by base type.

This pattern helps writing code that is decoupled (e.g. business layer logic separated
from exact implementations of data access logic).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from neoteroi.di import Container


@dataclass
class Cat:
    id: str
    name: str


class CatsRepository(ABC):
    @abstractmethod
    def get_cat(self, cat_id: str) -> Cat:
        """Gets information of a cat by ID."""


class SQLiteCatsRepository(CatsRepository):
    def get_cat(self, cat_id: str) -> Cat:
        """Gets information of a cat by ID, from a source SQLite DB."""
        raise NotImplementedError()


container = Container()

container.register(CatsRepository, SQLiteCatsRepository)

example_1 = container.resolve(CatsRepository)

assert isinstance(example_1, SQLiteCatsRepository)
