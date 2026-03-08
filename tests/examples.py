import uuid
from abc import ABC, abstractmethod
from typing import Optional


class Cat:
    def __init__(self, name: str):
        self.name = name


# abstract interface
class ICatsRepository(ABC):
    @abstractmethod
    def get_by_id(self, _id) -> Cat:
        pass


# one of the possible implementations of ICatsRepository
class InMemoryCatsRepository(ICatsRepository):
    def __init__(self):
        self._cats = {}

    def get_by_id(self, _id) -> Cat:
        return self._cats.get(_id)


# NB: example of business layer class, using interface of repository
class GetCatRequestHandler:
    def __init__(self, cats_repository: ICatsRepository):
        self.repo = cats_repository

    def get_cat(self, _id):
        cat = self.repo.get_by_id(_id)
        return cat


# NB: example of controller class;
class CatsController:
    def __init__(self, get_cat_request_handler: GetCatRequestHandler):
        self.cat_request_handler = get_cat_request_handler


class IRequestContext(ABC):
    @property
    @abstractmethod
    def id(self):
        pass

    @property
    @abstractmethod
    def user(self):
        pass


class RequestContext(IRequestContext):
    def __init__(self):
        pass

    @property
    def id(self):
        return "Example"

    @property
    def user(self):
        return "Example"


class ServiceSettings:
    def __init__(self, foo_db_connection_string):
        self.foo_db_connection_string = foo_db_connection_string


class FooDBContext:
    def __init__(self, service_settings: ServiceSettings):
        self.settings = service_settings
        self.connection_string = service_settings.foo_db_connection_string


class FooDBCatsRepository(ICatsRepository):
    def __init__(self, context: FooDBContext):
        self.context = context

    def get_by_id(self, _id) -> Cat:
        pass


class IValueProvider:
    @property
    @abstractmethod
    def value(self):
        pass


class ValueProvider(IValueProvider):
    __slots__ = "_value"

    def __init__(self, value):
        self._value = value

    @property
    def value(self):
        return self._value


class IdGetter:
    def __init__(self):
        self.value = uuid.uuid4()

    def __repr__(self):
        return f"<ID {str(self.value)}>"

    def __str__(self):
        return f"<ID {str(self.value)}>"


class A:
    def __init__(self, id_getter: IdGetter):
        self.id_getter = id_getter


class B:
    def __init__(self, a: A, id_getter: IdGetter):
        self.a = a
        self.id_getter = id_getter


class C:
    def __init__(self, a: A, b: B, id_getter: IdGetter):
        self.a = a
        self.b = b
        self.id_getter = id_getter


class ICircle(ABC):
    pass


class Circle(ICircle):
    def __init__(self, circular: ICircle):
        # NB: this is not supported by DI
        self.circular = circular


class Circle2(ICircle):
    circular: ICircle


class Shape:
    def __init__(self, circle: Circle):
        self.circle = circle


class Foo:
    def __init__(self):
        pass


class UfoOne:
    def __init__(self):
        pass


class UfoTwo:
    def __init__(self, one: UfoOne):
        self.one = one


class UfoThree(UfoTwo):
    def __init__(self, one: UfoOne, foo: Foo):
        super().__init__(one)
        self.foo = foo


class UfoFour(UfoThree):
    def __init__(self, one: UfoOne, foo: Foo):
        super().__init__(one, foo)


class TypeWithOptional:
    def __init__(self, foo: Optional[Foo]):
        self.foo = foo


class SelfReferencingCircle:
    def __init__(self, circle: "SelfReferencingCircle"):
        self.circular = circle


class TrickyCircle:
    def __init__(self, circle: ICircle):
        self.circular = circle


class ResolveThisByParameterName:
    def __init__(self, icats_repository):
        self.cats_repository = icats_repository


class IByParamName:
    pass


class FooByParamName(IByParamName):
    def __init__(self, foo):
        self.foo = foo


class Jing:
    def __init__(self, jang):
        self.jang = jang


class Jang:
    def __init__(self, jing):
        self.jing = jing


class Q:
    def __init__(self):
        pass


class R:
    def __init__(self, p):
        self.p = p


class P:
    def __init__(self):
        pass


class W:
    def __init__(self, x):
        self.x = x


class X:
    def __init__(self, y):
        self.y = y


class Y:
    def __init__(self, z):
        self.z = z


class Z:
    def __init__(self, w):
        self.w = w


class Ko:
    def __init__(self):
        pass


class Ok:
    def __init__(self):
        pass


class PrecedenceOfTypeHintsOverNames:
    def __init__(self, foo: Q, ko: P):
        self.q = foo
        self.p = ko


# Classes for testing mixed __init__ + class annotation injection


class MixedDep1:
    pass


class MixedDep2:
    pass


class MixedNoInitArgs:
    """Has a custom __init__ with no injectable args, plus class-level annotations."""

    injected: MixedDep1

    def __init__(self) -> None:
        self.value = "hello"


class MixedWithInitArgs:
    """
    Has a custom __init__ with injectable args, plus additional class-level
    annotations.
    """

    extra: MixedDep2

    def __init__(self, dep1: MixedDep1) -> None:
        self.dep1 = dep1
        self.value = "hello"


class MixedSingleton:
    """Singleton variant for mixed injection."""

    dep2: MixedDep2

    def __init__(self, dep1: MixedDep1) -> None:
        self.dep1 = dep1


class MixedScoped:
    """Scoped variant for mixed injection."""

    dep2: MixedDep2

    def __init__(self, dep1: MixedDep1) -> None:
        self.dep1 = dep1


class MixedAnnotationOverlapsInit:
    """
    Class where a class annotation name matches an __init__ parameter.
    The annotation should NOT be double-injected; init param takes precedence.
    """

    dep1: MixedDep1  # same name as __init__ param - should be handled by init only

    def __init__(self, dep1: MixedDep1) -> None:
        self.dep1 = dep1


# Classes for testing the decorator pattern


class IGreeter:
    def greet(self, name: str) -> str:
        raise NotImplementedError


class SimpleGreeter(IGreeter):
    def greet(self, name: str) -> str:
        return f"Hello, {name}"


class LoggingGreeter(IGreeter):
    """Decorator that logs calls before delegating to the inner greeter."""

    def __init__(self, inner: IGreeter) -> None:
        self.inner = inner
        self.calls: list = []

    def greet(self, name: str) -> str:
        self.calls.append(name)
        return self.inner.greet(name)


class ExclamatoryGreeter(IGreeter):
    """Second decorator that adds an exclamation mark."""

    def __init__(self, inner: IGreeter) -> None:
        self.inner = inner

    def greet(self, name: str) -> str:
        return self.inner.greet(name) + "!"


class Logger:
    """A simple logger dependency for decorator tests."""

    def __init__(self) -> None:
        self.messages: list = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class GreeterWithExtraDep(IGreeter):
    """Decorator that has both the decorated service and an additional dependency."""

    def __init__(self, inner: IGreeter, logger: Logger) -> None:
        self.inner = inner
        self.logger = logger

    def greet(self, name: str) -> str:
        self.logger.log(f"greet({name})")
        return self.inner.greet(name)


class DecoratorNoMatchingParam(IGreeter):
    """Decorator whose __init__ has no parameter matching IGreeter — invalid."""

    def __init__(self, logger: Logger) -> None:
        self.logger = logger

    def greet(self, name: str) -> str:
        return ""


class LoggingGreeterWithClassProp(IGreeter):
    """
    Decorator with the decoratee in __init__ and an extra dependency as a
    class-level annotation (property injection).
    """

    logger: Logger

    def __init__(self, inner: IGreeter) -> None:
        self.inner = inner

    def greet(self, name: str) -> str:
        self.logger.log(f"greet({name})")
        return self.inner.greet(name)
