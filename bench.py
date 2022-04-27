from timeit import timeit

from rodi import Container


class A:
    pass


class B:
    def __init__(self, a: A):
        self.a = a


class Dog:
    def __init__(self, b: B):
        self.b = b


class Cat:
    def __init__(self, dog: Dog):
        self.dog = dog


container = Container()
container.add_transient(A)
container.add_transient(B)
container.add_transient(Dog)
container.add_transient(Cat)

services = container.build_provider()  # --> validation, generation of functions

cat = services.get(Cat)

print(
    "services.get(Cat)",
    timeit(
        "do()",
        globals={"do": lambda: services.get(Cat)},
        number=100_000
    )
)

# Before mypyc: 0.28 - 0.33 average
# After mypyc:  0.13 - 0.16 average (mypyc rodi)
# Diff: ~2 times
