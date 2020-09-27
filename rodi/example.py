from abc import abstractmethod
from typing import Type, TypeVar, Dict, Callable, Any


T = TypeVar("T")


class Container:
    _map: Dict[Type[T], Callable[[], T]]

    def __init__(self) -> None:
        self._map = {}

    def add_singleton(self, item: T) -> None:
        self._map[type(item)] = lambda: item

    def add_transient_by_type(
        self, base_type: Type[Any], concrete_type: Type[T]
    ) -> None:
        self._map[base_type] = lambda: concrete_type()

    def get(self, desired_type: Type[T]) -> T:
        return self._map[desired_type]()


class ICat:
    @abstractmethod
    def meow(self) -> None:
        ...


class Cat(ICat):
    def meow(self) -> None:
        ...


if __name__ == "__main__":
    container = Container()

    container.add_singleton(20)

    element = container.get(int)

    container.add_singleton("Dupa")

    assert element == 20

    assert container.get(str) == "Dupa"

    container.add_transient_by_type(ICat, Cat)

    # mypy is disappointing here
    cat = container.get(ICat)

    assert isinstance(cat, Cat)
