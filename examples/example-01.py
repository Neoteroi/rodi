"""
This example illustrates a basic usage of the Container class to register
two types, and automatic resolution achieved through types inspection.

Two services are registered as "transient" services, meaning that a new instance is
created whenever needed.
"""

from neoteroi.di import Container


class A:
    pass


class B:
    friend: A


container = Container()

container.register(A)
container.register(B)

example_1 = container.resolve(B)

assert isinstance(example_1, B)
assert isinstance(example_1.friend, A)


example_2 = container.resolve(B)

assert isinstance(example_2, B)
assert isinstance(example_2.friend, A)

assert example_1 is not example_2
