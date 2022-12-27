"""
This example illustrates how to configure a singleton object.
"""
from dataclasses import dataclass

from neoteroi.di import Container


@dataclass
class Cat:
    id: str
    name: str


# Using the ContainerProtocol (recommended if it is desirable to possibly replace the
# library with an alternative implementation of dependency injection)
container = Container()

container.register(Cat, instance=Cat("1", "Celine"))

example = container.resolve(Cat)

assert isinstance(example, Cat)
assert example.id == "1" and example.name == "Celine"

assert example is container.resolve(Cat)


# Using the original code API
class Foo:
    ...


container.add_instance(Foo())

assert container.resolve(Foo) is container.resolve(Foo)
