import sys
from abc import ABC
from dataclasses import dataclass
from typing import (
    ClassVar,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

import pytest
from pytest import raises

from rodi import (
    ActivationScope,
    AliasAlreadyDefined,
    AliasConfigurationError,
    CannotResolveParameterException,
    CannotResolveTypeException,
    CircularDependencyException,
    Container,
    ContainerProtocol,
    DynamicResolver,
    FactoryMissingContextException,
    InstanceResolver,
    InvalidFactory,
    InvalidOperationInStrictMode,
    MissingTypeException,
    OverridingServiceException,
    ServiceLifeStyle,
    Services,
    UnsupportedUnionTypeException,
    _get_factory_annotations_or_throw,
    inject,
    to_standard_param_name,
)
from tests.examples import (
    A,
    B,
    C,
    Cat,
    CatsController,
    Circle,
    Circle2,
    Foo,
    FooByParamName,
    FooDBCatsRepository,
    FooDBContext,
    GetCatRequestHandler,
    IByParamName,
    ICatsRepository,
    ICircle,
    IdGetter,
    InMemoryCatsRepository,
    IRequestContext,
    Jang,
    Jing,
    Ko,
    Ok,
    P,
    PrecedenceOfTypeHintsOverNames,
    Q,
    R,
    RequestContext,
    ResolveThisByParameterName,
    ServiceSettings,
    Shape,
    TrickyCircle,
    TypeWithOptional,
    UfoFour,
    UfoOne,
    UfoThree,
    UfoTwo,
    W,
    X,
    Y,
    Z,
)

T_1 = TypeVar("T_1")


try:
    from typing import Protocol
except ImportError:  # pragma: no cover
    # support for Python 3.7
    from typing_extensions import Protocol


class LoggedVar(Generic[T_1]):
    def __init__(self, value: T_1, name: str) -> None:
        self.name = name
        self.value = value

    def set(self, new: T_1) -> None:
        self.log("Set " + repr(self.value))
        self.value = new

    def get(self) -> T_1:
        self.log("Get " + repr(self.value))
        return self.value

    def log(self, message: str) -> None:
        print(self.name, message)


def arrange_cats_example():
    container = Container()
    container.add_transient(ICatsRepository, FooDBCatsRepository)
    container.add_scoped(IRequestContext, RequestContext)
    container._add_exact_transient(GetCatRequestHandler)
    container._add_exact_transient(CatsController)
    container.add_instance(ServiceSettings("foodb:example;something;"))
    container._add_exact_transient(FooDBContext)
    return container


@pytest.mark.parametrize(
    "value,expected_result",
    (
        ("CamelCase", "camel_case"),
        ("HTTPResponse", "http_response"),
        ("ICatsRepository", "icats_repository"),
        ("Cat", "cat"),
        ("UFO", "ufo"),
    ),
)
def test_standard_param_name(value, expected_result):
    snaked = to_standard_param_name(value)
    assert snaked == expected_result


def test_singleton_by_instance():
    container = Container()
    container.add_instance(Cat("Celine"))
    provider = container.build_provider()

    cat = provider.get(Cat)

    assert cat is not None
    assert cat.name == "Celine"


def test_transient_by_type_without_parameters():
    container = Container()
    container.add_transient(ICatsRepository, InMemoryCatsRepository)
    provider = container.build_provider()
    cats_repo = provider.get(ICatsRepository)

    assert isinstance(cats_repo, InMemoryCatsRepository)
    other_cats_repo = provider.get(ICatsRepository)

    assert isinstance(other_cats_repo, InMemoryCatsRepository)
    assert cats_repo is not other_cats_repo


def test_transient_by_type_with_parameters():
    container = Container()
    container.add_transient(ICatsRepository, FooDBCatsRepository)

    # NB:
    container.add_instance(ServiceSettings("foodb:example;something;"))
    container._add_exact_transient(FooDBContext)
    provider = container.build_provider()

    cats_repo = provider.get(ICatsRepository)

    assert isinstance(cats_repo, FooDBCatsRepository)
    assert isinstance(cats_repo.context, FooDBContext)
    assert isinstance(cats_repo.context.settings, ServiceSettings)
    assert cats_repo.context.connection_string == "foodb:example;something;"


def test_add_transient_shortcut():
    container = Container()
    container.add_transient(ICatsRepository, FooDBCatsRepository)

    # NB:
    container.add_instance(ServiceSettings("foodb:example;something;"))
    container.add_transient(FooDBContext)
    provider = container.build_provider()

    cats_repo = provider.get(ICatsRepository)

    assert isinstance(cats_repo, FooDBCatsRepository)
    assert isinstance(cats_repo.context, FooDBContext)
    assert isinstance(cats_repo.context.settings, ServiceSettings)
    assert cats_repo.context.connection_string == "foodb:example;something;"


def test_raises_for_overriding_service():
    container = Container()
    container.add_transient(ICircle, Circle)

    with pytest.raises(OverridingServiceException) as context:
        container.add_singleton(ICircle, Circle)

    assert "ICircle" in str(context.value)

    with pytest.raises(OverridingServiceException) as context:
        container.add_transient(ICircle, Circle)

    assert "ICircle" in str(context.value)

    with pytest.raises(OverridingServiceException) as context:
        container.add_scoped(ICircle, Circle)

    assert "ICircle" in str(context.value)


def test_raises_for_circular_dependency():
    container = Container()
    container.add_transient(ICircle, Circle)

    with pytest.raises(CircularDependencyException) as context:
        container.build_provider()

    assert "Circle" in str(context.value)


def test_raises_for_circular_dependency_class_annotation():
    container = Container()
    container.add_transient(ICircle, Circle2)

    with pytest.raises(CircularDependencyException) as context:
        container.build_provider()

    assert "Circle" in str(context.value)


def test_raises_for_circular_dependency_with_dynamic_resolver():
    container = Container()
    container._add_exact_transient(Jing)
    container._add_exact_transient(Jang)

    with pytest.raises(CircularDependencyException):
        container.build_provider()


def test_raises_for_deep_circular_dependency_with_dynamic_resolver():
    container = Container()
    container._add_exact_transient(W)
    container._add_exact_transient(X)
    container._add_exact_transient(Y)
    container._add_exact_transient(Z)

    with pytest.raises(CircularDependencyException):
        container.build_provider()


def test_does_not_raise_for_deep_circular_dependency_with_one_factory():
    container = Container()
    container._add_exact_transient(W)
    container._add_exact_transient(X)
    container._add_exact_transient(Y)

    def z_factory(_) -> Z:
        return Z(None)

    container.add_transient_by_factory(z_factory)

    provider = container.build_provider()

    w = provider.get(W)

    assert isinstance(w, W)
    assert isinstance(w.x, X)
    assert isinstance(w.x.y, Y)
    assert isinstance(w.x.y.z, Z)
    assert w.x.y.z.w is None


def test_circular_dependency_is_supported_by_factory():
    def get_jang(_) -> Jang:
        return Jang(None)

    container = Container()
    container._add_exact_transient(Jing)
    container.add_transient_by_factory(get_jang)

    provider = container.build_provider()

    jing = provider.get(Jing)
    assert jing is not None
    assert isinstance(jing.jang, Jang)
    assert jing.jang.jing is None


def test_add_instance_allows_for_circular_classes():
    container = Container()
    container.add_instance(Circle(Circle(None)))

    # NB: in this example, Shape requires a Circle
    container._add_exact_transient(Shape)
    provider = container.build_provider()

    circle = provider.get(Circle)
    assert isinstance(circle, Circle)

    shape = provider.get(Shape)

    assert isinstance(shape, Shape)
    assert shape.circle is circle


def test_add_instance_with_declared_type():
    container = Container()
    container.add_instance(Circle(Circle(None)), declared_class=ICircle)
    provider = container.build_provider()

    icircle = provider.get(ICircle)
    assert isinstance(icircle, Circle)


def test_raises_for_optional_parameter():
    container = Container()
    container._add_exact_transient(Foo)
    container._add_exact_transient(TypeWithOptional)

    with pytest.raises(UnsupportedUnionTypeException) as context:
        container.build_provider()

    assert "foo" in str(context.value)


def test_raises_for_nested_circular_dependency():
    container = Container()
    container.add_transient(ICircle, Circle)
    container._add_exact_transient(TrickyCircle)

    with pytest.raises(CircularDependencyException) as context:
        container.build_provider()

    assert "Circle" in str(context.value)


def test_interdependencies():
    container = Container()
    container._add_exact_transient(A)
    container._add_exact_transient(B)
    container._add_exact_transient(C)
    container._add_exact_transient(IdGetter)
    provider = container.build_provider()

    c = provider.get(C)

    assert isinstance(c, C)
    assert isinstance(c.a, A)
    assert isinstance(c.b, B)
    assert isinstance(c.b.a, A)


def test_transient_service():
    container = Container()
    container.add_transient(ICatsRepository, InMemoryCatsRepository)
    provider = container.build_provider()

    cats_repo = provider.get(ICatsRepository)
    assert isinstance(cats_repo, InMemoryCatsRepository)

    other_cats_repo = provider.get(ICatsRepository)
    assert cats_repo is not other_cats_repo


def test_singleton_services():
    container = Container()
    container._add_exact_singleton(IdGetter)
    provider = container.build_provider()

    with ActivationScope() as context:
        a = provider.get(IdGetter, context)
        b = provider.get(IdGetter, context)
        c = provider.get(IdGetter, context)
    d = provider.get(IdGetter)

    assert a is b
    assert a is c
    assert b is c
    assert d is a


def test_scoped_services_context_used_more_than_once():
    container = Container()

    @inject()
    class C:
        def __init__(self):
            pass

    @inject()
    class B2:
        def __init__(self, c: C):
            self.c = c

    @inject()
    class B1:
        def __init__(self, c: C):
            self.c = c

    @inject()
    class A:
        def __init__(self, b1: B1, b2: B2):
            self.b1 = b1
            self.b2 = b2

    container._add_exact_scoped(C)
    container._add_exact_transient(B1)
    container._add_exact_transient(B2)
    container._add_exact_transient(A)

    provider = container.build_provider()

    context = ActivationScope(provider)

    with context:
        a = provider.get(A, context)
        first_c = provider.get(C)
        a.b1.c is first_c
        a.b2.c is first_c

    with context:
        a = provider.get(A, context)
        second_c = provider.get(C)
        a.b1.c is second_c
        a.b2.c is second_c

    assert first_c is not None
    assert second_c is not None
    assert first_c is not second_c


def test_scoped_services_context_used_more_than_once_manual_dispose():
    container = Container()

    container.add_instance("value")

    provider = container.build_provider()
    context = ActivationScope(provider)

    context.dispose()
    assert context.provider is None


def test_transient_services():
    container = Container()
    container._add_exact_transient(IdGetter)
    provider = container.build_provider()

    with ActivationScope() as context:
        a = provider.get(IdGetter, context)
        b = provider.get(IdGetter, context)
        c = provider.get(IdGetter, context)
    d = provider.get(IdGetter)

    assert a is not b
    assert a is not c
    assert b is not c
    assert d is not a
    assert d is not b
    assert d is not c


def test_scoped_services():
    container = Container()
    container._add_exact_scoped(IdGetter)
    provider = container.build_provider()

    with ActivationScope() as context:
        a = provider.get(IdGetter, context)
        b = provider.get(IdGetter, context)
        c = provider.get(IdGetter, context)
    d = provider.get(IdGetter)

    assert a is b
    assert b is c
    assert a is not d
    assert b is not d


def test_scopeed_service_from_scoped_services():
    container = Container()
    provider = container.build_provider()

    scoped_service = IdGetter()

    with ActivationScope(provider, {
        IdGetter: scoped_service,
    }) as context:
        a = provider.get(IdGetter, context)
        b = provider.get(IdGetter, default=None)
    c = provider.get(IdGetter, default=None)

    assert a is scoped_service
    assert b is None
    assert c is None


def test_scoped_services_with_shortcut():
    container = Container()
    container.add_scoped(IdGetter)
    provider = container.build_provider()

    with ActivationScope() as context:
        a = provider.get(IdGetter, context)
        b = provider.get(IdGetter, context)
        c = provider.get(IdGetter, context)
    d = provider.get(IdGetter)

    assert a is b
    assert b is c
    assert a is not d
    assert b is not d


def test_resolution_by_parameter_name():
    container = Container()
    container.add_transient(ICatsRepository, InMemoryCatsRepository)
    container._add_exact_transient(ResolveThisByParameterName)

    provider = container.build_provider()
    resolved = provider.get(ResolveThisByParameterName)

    assert resolved is not None

    assert isinstance(resolved, ResolveThisByParameterName)
    assert isinstance(resolved.cats_repository, InMemoryCatsRepository)


def test_resolve_singleton_by_parameter_name():
    container = Container()
    container.add_transient(IByParamName, FooByParamName)

    singleton = Foo()
    container.add_instance(singleton)

    provider = container.build_provider()
    resolved = provider.get(IByParamName)

    assert resolved is not None

    assert isinstance(resolved, FooByParamName)
    assert resolved.foo is singleton


def test_service_collection_contains():
    container = Container()
    container._add_exact_transient(Foo)

    assert Foo in container
    assert Cat not in container


def test_service_provider_contains():
    container = Container()
    container.add_transient(IdGetter)

    provider = container.build_provider()

    assert Foo not in provider
    assert IdGetter in provider


def test_exact_alias():
    container = arrange_cats_example()

    class UsingAlias:
        def __init__(self, example):
            self.cats_controller = example

    container.add_transient(UsingAlias)

    # arrange an exact alias for UsingAlias class init parameter:
    container.set_alias("example", CatsController)

    provider = container.build_provider()
    u = provider.get(UsingAlias)

    assert isinstance(u, UsingAlias)
    assert isinstance(u.cats_controller, CatsController)
    assert isinstance(u.cats_controller.cat_request_handler, GetCatRequestHandler)


def test_additional_alias():
    container = arrange_cats_example()

    class UsingAlias:
        def __init__(self, example, settings):
            self.cats_controller = example
            self.settings = settings

    class AnotherUsingAlias:
        def __init__(self, cats_controller, service_settings):
            self.cats_controller = cats_controller
            self.settings = service_settings

    container._add_exact_transient(UsingAlias)
    container._add_exact_transient(AnotherUsingAlias)

    # arrange an exact alias for UsingAlias class init parameter:
    container.add_alias("example", CatsController)
    container.add_alias("settings", ServiceSettings)

    provider = container.build_provider()
    u = provider.get(UsingAlias)

    assert isinstance(u, UsingAlias)
    assert isinstance(u.settings, ServiceSettings)
    assert isinstance(u.cats_controller, CatsController)
    assert isinstance(u.cats_controller.cat_request_handler, GetCatRequestHandler)

    u = provider.get(AnotherUsingAlias)

    assert isinstance(u, AnotherUsingAlias)
    assert isinstance(u.settings, ServiceSettings)
    assert isinstance(u.cats_controller, CatsController)
    assert isinstance(u.cats_controller.cat_request_handler, GetCatRequestHandler)


def test_get_service_by_name_or_alias():
    container = arrange_cats_example()
    container.add_alias("k", CatsController)

    provider = container.build_provider()

    for name in {"CatsController", "cats_controller", "k"}:
        service = provider.get(name)

        assert isinstance(service, CatsController)
        assert isinstance(service.cat_request_handler, GetCatRequestHandler)
        assert isinstance(service.cat_request_handler.repo, FooDBCatsRepository)


def test_missing_service_raises_exception():
    container = Container()
    provider = container.build_provider()

    with pytest.raises(CannotResolveTypeException):
        provider.get("not_existing")


def test_missing_service_can_return_default():
    container = Container()
    provider = container.build_provider()

    service = provider.get("not_existing", default=None)
    assert service is None


def test_by_factory_type_annotation_simple():
    container = Container()

    def factory() -> Cat:
        return Cat("Celine")

    container.add_transient_by_factory(factory)
    provider = container.build_provider()

    cat = provider.get(Cat)
    assert isinstance(cat, Cat)
    assert cat.name == "Celine"


def test_by_factory_type_annotation_simple_local():
    container = Container()

    @dataclass
    class LocalCat:
        name: str

    @inject()
    def service_factory() -> LocalCat:
        return LocalCat("Celine")

    container.add_transient_by_factory(service_factory)
    provider = container.build_provider()

    cat = provider.get(LocalCat)
    assert isinstance(cat, LocalCat)
    assert cat.name == "Celine"


@pytest.mark.parametrize(
    "method_name",
    ["add_singleton_by_factory", "add_transient_by_factory", "add_scoped_by_factory"],
)
def test_by_factory_type_annotation(method_name):
    container = Container()

    def factory(_) -> Cat:
        return Cat("Celine")

    method = getattr(container, method_name)

    method(factory)

    provider = container.build_provider()

    cat = provider.get(Cat)

    assert cat is not None
    assert cat.name == "Celine"

    if method_name == "add_singleton_by_factory":
        cat_2 = provider.get(Cat)
        assert cat_2 is cat

    if method_name == "add_transient_by_factory":
        assert provider.get(Cat) is not cat
        assert provider.get(Cat) is not cat
        assert provider.get(Cat) is not cat

    if method_name == "add_scoped_by_factory":
        with ActivationScope() as context:
            cat_2 = provider.get(Cat, context)
            assert cat_2 is not cat

            assert provider.get(Cat, context) is cat_2
            assert provider.get(Cat, context) is cat_2
            assert provider.get(Cat, context) is cat_2


@pytest.mark.parametrize(
    "method_name",
    ["add_singleton_by_factory", "add_transient_by_factory", "add_scoped_by_factory"],
)
def test_invalid_factory_too_many_arguments_throws(method_name):
    container = Container()
    method = getattr(container, method_name)

    def factory(context, activating_type, extra_argument_mistake):
        return Cat("Celine")

    with raises(InvalidFactory):
        method(factory, Cat)

    def factory(context, activating_type, extra_argument_mistake, two):
        return Cat("Celine")

    with raises(InvalidFactory):
        method(factory, Cat)

    def factory(context, activating_type, extra_argument_mistake, two, three):
        return Cat("Celine")

    with raises(InvalidFactory):
        method(factory, Cat)


@pytest.mark.parametrize(
    "method_name",
    ["add_singleton_by_factory", "add_transient_by_factory", "add_scoped_by_factory"],
)
def test_add_singleton_by_factory_given_type(method_name):
    container = Container()

    def factory(a):
        return Cat("Celine")

    method = getattr(container, method_name)

    method(factory, Cat)

    provider = container.build_provider()

    cat = provider.get(Cat)

    assert cat is not None
    assert cat.name == "Celine"

    if method_name == "add_singleton_by_factory":
        cat_2 = provider.get(Cat)
        assert cat_2 is cat

    if method_name == "add_transient_by_factory":
        assert provider.get(Cat) is not cat
        assert provider.get(Cat) is not cat
        assert provider.get(Cat) is not cat

    if method_name == "add_scoped_by_factory":
        with ActivationScope() as context:
            cat_2 = provider.get(Cat, context)
            assert cat_2 is not cat

            assert provider.get(Cat, context) is cat_2
            assert provider.get(Cat, context) is cat_2
            assert provider.get(Cat, context) is cat_2


@pytest.mark.parametrize(
    "method_name",
    ["add_singleton_by_factory", "add_transient_by_factory", "add_scoped_by_factory"],
)
def test_add_singleton_by_factory_raises_for_missing_type(method_name):
    container = Container()

    def factory(_):
        return Cat("Celine")

    method = getattr(container, method_name)

    with pytest.raises(MissingTypeException):
        method(factory)


def test_singleton_by_provider():
    container = Container()
    container._add_exact_singleton(P)
    container._add_exact_transient(R)

    provider = container.build_provider()

    p = provider.get(P)
    r = provider.get(R)

    assert p is not None
    assert r is not None
    assert r.p is p


def test_singleton_by_provider_with_shortcut():
    container = Container()
    container.add_singleton(P)
    container.add_transient(R)

    provider = container.build_provider()

    p = provider.get(P)
    r = provider.get(R)

    assert p is not None
    assert r is not None
    assert r.p is p


def test_singleton_by_provider_both_singletons():
    container = Container()
    container._add_exact_singleton(P)
    container._add_exact_singleton(R)

    provider = container.build_provider()

    p = provider.get(P)
    r = provider.get(R)

    assert p is not None
    assert r is not None
    assert r.p is p

    r_2 = provider.get(R)
    assert r_2 is r


def test_type_hints_precedence():
    container = Container()
    container._add_exact_transient(PrecedenceOfTypeHintsOverNames)
    container._add_exact_transient(Foo)
    container._add_exact_transient(Q)
    container._add_exact_transient(P)
    container._add_exact_transient(Ko)
    container._add_exact_transient(Ok)

    provider = container.build_provider()

    service = provider.get(PrecedenceOfTypeHintsOverNames)

    assert isinstance(service, PrecedenceOfTypeHintsOverNames)
    assert isinstance(service.q, Q)
    assert isinstance(service.p, P)


def test_type_hints_precedence_with_shortcuts():
    container = Container()
    container.add_transient(PrecedenceOfTypeHintsOverNames)
    container.add_transient(Foo)
    container.add_transient(Q)
    container.add_transient(P)
    container.add_transient(Ko)
    container.add_transient(Ok)

    provider = container.build_provider()

    service = provider.get(PrecedenceOfTypeHintsOverNames)

    assert isinstance(service, PrecedenceOfTypeHintsOverNames)
    assert isinstance(service.q, Q)
    assert isinstance(service.p, P)


def test_proper_handling_of_inheritance():
    container = Container()
    container._add_exact_transient(UfoOne)
    container._add_exact_transient(UfoTwo)
    container._add_exact_transient(UfoThree)
    container._add_exact_transient(UfoFour)
    container._add_exact_transient(Foo)

    provider = container.build_provider()

    ufo_one = provider.get(UfoOne)
    ufo_two = provider.get(UfoTwo)
    ufo_three = provider.get(UfoThree)
    ufo_four = provider.get(UfoFour)

    assert isinstance(ufo_one, UfoOne)
    assert isinstance(ufo_two, UfoTwo)
    assert isinstance(ufo_three, UfoThree)
    assert isinstance(ufo_four, UfoFour)


def cat_factory_no_args() -> Cat:
    return Cat("Celine")


def cat_factory_with_context(context) -> Cat:
    assert isinstance(context, ActivationScope)
    return Cat("Celine")


def cat_factory_with_context_and_activating_type(context, activating_type) -> Cat:
    assert isinstance(context, ActivationScope)
    assert activating_type is Cat
    return Cat("Celine")


@pytest.mark.parametrize(
    "method_name,factory",
    [
        (name, method)
        for name in [
            "add_singleton_by_factory",
            "add_transient_by_factory",
            "add_scoped_by_factory",
        ]
        for method in [
            cat_factory_no_args,
            cat_factory_with_context,
            cat_factory_with_context_and_activating_type,
        ]
    ],
)
def test_by_factory_with_different_parameters(method_name, factory):
    container = Container()

    method = getattr(container, method_name)
    method(factory)

    provider = container.build_provider()

    cat = provider.get(Cat)

    assert cat is not None
    assert cat.name == "Celine"


@pytest.mark.parametrize(
    "method_name", ["add_transient_by_factory", "add_scoped_by_factory"]
)
def test_factory_can_receive_activating_type_as_parameter(method_name):
    @inject()
    class Logger:
        def __init__(self, name):
            self.name = name

    @inject()
    class HelpController:
        def __init__(self, logger: Logger):
            self.logger = logger

    @inject()
    class HomeController:
        def __init__(self, logger: Logger):
            self.logger = logger

    @inject()
    class FooController:
        def __init__(self, foo: Foo, logger: Logger):
            self.foo = foo
            self.logger = logger

    container = Container()
    container._add_exact_transient(Foo)

    @inject()
    def factory(_, activating_type) -> Logger:
        return Logger(activating_type.__module__ + "." + activating_type.__name__)

    method = getattr(container, method_name)
    method(factory)

    container._add_exact_transient(HelpController)._add_exact_transient(
        HomeController
    )._add_exact_transient(FooController)

    provider = container.build_provider()

    help_controller = provider.get(HelpController)

    assert help_controller is not None
    assert help_controller.logger is not None
    assert help_controller.logger.name == "tests.test_services.HelpController"

    home_controller = provider.get(HomeController)

    assert home_controller is not None
    assert home_controller.logger is not None
    assert home_controller.logger.name == "tests.test_services.HomeController"

    foo_controller = provider.get(FooController)

    assert foo_controller is not None
    assert foo_controller.logger is not None
    assert foo_controller.logger.name == "tests.test_services.FooController"


def test_factory_can_receive_activating_type_as_parameter_nested_resolution():
    # NB: this scenario can only work when a class is registered as transient service

    class Logger:
        def __init__(self, name):
            self.name = name

    @inject()
    class HelpRepo:
        def __init__(self, logger: Logger):
            self.logger = logger

    @inject()
    class HelpHandler:
        def __init__(self, help_repo: HelpRepo):
            self.repo = help_repo

    @inject()
    class HelpController:
        def __init__(self, logger: Logger, handler: HelpHandler):
            self.logger = logger
            self.handler = handler

    container = Container()

    @inject()
    def factory(_, activating_type) -> Logger:
        # NB: this scenario is tested for rolog library
        return Logger(activating_type.__module__ + "." + activating_type.__name__)

    container.add_transient_by_factory(factory)

    for service_type in {HelpRepo, HelpHandler, HelpController}:
        container._add_exact_transient(service_type)

    provider = container.build_provider()

    help_controller = provider.get(HelpController)

    assert help_controller is not None
    assert help_controller.logger is not None
    assert help_controller.logger.name == "tests.test_services.HelpController"
    assert help_controller.handler.repo.logger.name == "tests.test_services.HelpRepo"


def test_factory_can_receive_activating_type_as_parameter_nested_resolution_many():
    # NB: this scenario can only work when a class is registered as transient service

    class Logger:
        def __init__(self, name):
            self.name = name

    @inject()
    class HelpRepo:
        def __init__(self, db_context: FooDBContext, logger: Logger):
            self.db_context = db_context
            self.logger = logger

    @inject()
    class HelpHandler:
        def __init__(self, help_repo: HelpRepo):
            self.repo = help_repo

    @inject()
    class AnotherPathTwo:
        def __init__(self, logger: Logger):
            self.logger = logger

    @inject()
    class AnotherPath:
        def __init__(self, another_path_2: AnotherPathTwo):
            self.child = another_path_2

    @inject()
    class HelpController:
        def __init__(
            self, handler: HelpHandler, another_path: AnotherPath, logger: Logger
        ):
            self.logger = logger
            self.handler = handler
            self.other = another_path

    container = Container()

    @inject()
    def factory(_, activating_type) -> Logger:
        # NB: this scenario is tested for rolog library
        return Logger(activating_type.__module__ + "." + activating_type.__name__)

    container.add_transient_by_factory(factory)
    container.add_instance(ServiceSettings("foo:foo"))

    for service_type in {
        HelpRepo,
        HelpHandler,
        HelpController,
        AnotherPath,
        AnotherPathTwo,
        Foo,
        FooDBContext,
    }:
        container._add_exact_transient(service_type)

    provider = container.build_provider()

    help_controller = provider.get(HelpController)

    assert help_controller is not None
    assert help_controller.logger is not None
    assert help_controller.logger.name == "tests.test_services.HelpController"
    assert help_controller.handler.repo.logger.name == "tests.test_services.HelpRepo"
    assert (
        help_controller.other.child.logger.name == "tests.test_services."
        "AnotherPathTwo"
    )


def test_service_provider_supports_set_by_class():
    provider = Services()

    singleton_cat = Cat("Celine")

    provider.set(Cat, singleton_cat)

    cat = provider.get(Cat)

    assert cat is not None
    assert cat.name == "Celine"

    cat = provider.get("Cat")

    assert cat is not None
    assert cat.name == "Celine"


def test_service_provider_supports_set_by_name():
    provider = Services()

    singleton_cat = Cat("Celine")

    provider.set("my_cat", singleton_cat)

    cat = provider.get("my_cat")

    assert cat is not None
    assert cat.name == "Celine"


def test_service_provider_supports_set_and_get_item_by_class():
    provider = Services()

    singleton_cat = Cat("Celine")

    provider[Cat] = singleton_cat

    cat = provider[Cat]

    assert cat is not None
    assert cat.name == "Celine"

    cat = provider["Cat"]

    assert cat is not None
    assert cat.name == "Celine"


def test_service_provider_supports_set_and_get_item_by_name():
    provider = Services()

    singleton_cat = Cat("Celine")

    provider["my_cat"] = singleton_cat

    cat = provider["my_cat"]

    assert cat is not None
    assert cat.name == "Celine"


def test_service_provider_supports_set_simple_values():
    provider = Services()

    provider["one"] = 10
    provider["two"] = 12
    provider["three"] = 16

    assert provider["one"] == 10
    assert provider["two"] == 12
    assert provider["three"] == 16


def test_container_handles_class_without_init():
    container = Container()

    class WithoutInit:
        pass

    container._add_exact_singleton(WithoutInit)
    provider = container.build_provider()

    instance = provider.get(WithoutInit)
    assert isinstance(instance, WithoutInit)


def test_raises_invalid_factory_for_non_callable():
    container = Container()

    with raises(InvalidFactory):
        container.register_factory("Not a factory", Cat, ServiceLifeStyle.SINGLETON)


def test_set_alias_raises_in_strict_mode():
    container = Container(strict=True)

    with raises(InvalidOperationInStrictMode):
        container.set_alias("something", Cat)


def test_set_alias_raises_if_alias_is_defined():
    container = Container()

    container.set_alias("something", Cat)

    with raises(AliasAlreadyDefined):
        container.set_alias("something", Foo)


def test_set_alias_requires_configured_type():
    container = Container()

    container.set_alias("something", Cat)

    with raises(AliasConfigurationError):
        container.build_provider()


def test_set_aliases():
    container = Container()

    container.add_instance(Cat("Celine"))
    container.add_instance(Foo())

    container.set_aliases({"a": Cat, "b": Foo})

    provider = container.build_provider()

    x = provider.get("a")

    assert isinstance(x, Cat)
    assert x.name == "Celine"

    assert isinstance(provider.get("b"), Foo)


def test_add_alias_raises_in_strict_mode():
    container = Container(strict=True)

    with raises(InvalidOperationInStrictMode):
        container.add_alias("something", Cat)


def test_add_alias_raises_if_alias_is_defined():
    container = Container()

    container.add_alias("something", Cat)

    with raises(AliasAlreadyDefined):
        container.add_alias("something", Foo)


def test_add_aliases():
    container = Container()

    container.add_instance(Cat("Celine"))
    container.add_instance(Foo())

    container.add_aliases({"a": Cat, "b": Foo})

    container.add_aliases({"c": Cat, "d": Foo})

    provider = container.build_provider()

    for alias in {"a", "c"}:
        x = provider.get(alias)

        assert isinstance(x, Cat)
        assert x.name == "Celine"

    for alias in {"b", "d"}:
        assert isinstance(provider.get(alias), Foo)


def test_add_alias_requires_configured_type():
    container = Container()

    container.add_alias("something", Cat)

    with raises(AliasConfigurationError):
        container.build_provider()


def test_build_provider_raises_for_missing_transient_parameter():
    container = Container()

    container._add_exact_transient(CatsController)

    with raises(CannotResolveParameterException):
        container.build_provider()


def test_build_provider_raises_for_missing_scoped_parameter():
    container = Container()

    container._add_exact_scoped(CatsController)

    with raises(CannotResolveParameterException):
        container.build_provider()


def test_build_provider_raises_for_missing_singleton_parameter():
    container = Container()

    container._add_exact_singleton(CatsController)

    with raises(CannotResolveParameterException):
        container.build_provider()


def test_overriding_alias_from_class_name_throws():
    container = Container()

    class A:
        def __init__(self, b):
            self.b = b

    class B:
        def __init__(self, c):
            self.c = c

    class C:
        def __init__(self):
            pass

    container._add_exact_transient(A)
    container._add_exact_transient(B)
    container._add_exact_transient(C)

    with raises(AliasAlreadyDefined):
        container.add_alias("b", C)  # <-- ambiguity


def test_cannot_resolve_parameter_in_strict_mode_throws():
    container = Container(strict=True)

    class A:
        def __init__(self, b):
            self.b = b

    class B:
        def __init__(self, c):
            self.c = c

    container._add_exact_transient(A)
    container._add_exact_transient(B)

    with raises(CannotResolveParameterException):
        container.build_provider()


def test_services_set_throws_if_service_is_already_defined():
    services = Services()

    services.set("example", {})

    with raises(OverridingServiceException):
        services.set("example", [])


def test_scoped_services_exact():
    container = Container()

    class A:
        def __init__(self, b):
            self.b = b

    class B:
        def __init__(self, c):
            self.c = c

    class C:
        def __init__(self):
            pass

    container._add_exact_scoped(A)
    container._add_exact_scoped(B)
    container._add_exact_scoped(C)

    provider = container.build_provider()
    context = ActivationScope(provider)

    a = provider.get(A, context)
    assert isinstance(a, A)
    assert isinstance(a.b, B)
    assert isinstance(a.b.c, C)

    a2 = provider.get(A, context)
    assert a is a2
    assert a.b is a2.b
    assert a.b.c is a2.b.c


def test_scoped_services_abstract():
    container = Container()

    class ABase(ABC):
        pass

    class BBase(ABC):
        pass

    class CBase(ABC):
        pass

    @inject()
    class A(ABase):
        def __init__(self, b: BBase):
            self.b = b

    @inject()
    class B(BBase):
        def __init__(self, c: CBase):
            self.c = c

    class C(CBase):
        def __init__(self):
            pass

    container.add_scoped(ABase, A)
    container.add_scoped(BBase, B)
    container.add_scoped(CBase, C)

    provider = container.build_provider()
    context = ActivationScope(provider)

    a = provider.get(ABase, context)
    assert isinstance(a, A)
    assert isinstance(a.b, B)
    assert isinstance(a.b.c, C)

    a2 = provider.get(ABase, context)
    assert a is a2
    assert a.b is a2.b
    assert a.b.c is a2.b.c


def test_instance_resolver_representation():
    singleton = Foo()
    resolver = InstanceResolver(singleton)

    representation = repr(resolver)
    assert representation.startswith("<Singleton ")
    assert "Foo" in representation


@pytest.mark.parametrize(
    "method_name",
    ["add_transient_by_factory", "add_scoped_by_factory", "add_singleton_by_factory"],
)
def test_factories_activating_transient_type_consistency(method_name):
    container = Container()

    class ABase(ABC):
        pass

    class BBase(ABC):
        pass

    @inject()
    class A(ABase):
        def __init__(self, b: BBase):
            self.b = b

    class B(BBase):
        def __init__(self):
            pass

    @inject()
    def bbase_factory(context: ActivationScope, activating_type: Type) -> BBase:
        assert isinstance(context, ActivationScope)
        assert activating_type is A
        return B()

    container.add_transient(ABase, A)

    method = getattr(container, method_name)
    method(bbase_factory)

    provider = container.build_provider()
    context = ActivationScope(provider)

    a = provider.get(ABase, context)
    assert isinstance(a, A)
    assert isinstance(a.b, B)


@pytest.mark.parametrize(
    "method_name",
    ["add_transient_by_factory", "add_scoped_by_factory", "add_singleton_by_factory"],
)
def test_factories_activating_scoped_type_consistency(method_name):
    container = Container()

    class ABase(ABC):
        pass

    class BBase(ABC):
        pass

    @inject()
    class A(ABase):
        def __init__(self, b: BBase):
            self.b = b

    class B(BBase):
        def __init__(self):
            pass

    @inject()
    def bbase_factory(context: ActivationScope, activating_type: Type) -> BBase:
        assert isinstance(context, ActivationScope)
        assert activating_type is A
        return B()

    container.add_scoped(ABase, A)

    method = getattr(container, method_name)
    method(bbase_factory)

    provider = container.build_provider()
    context = ActivationScope(provider)

    a = provider.get(ABase, context)
    assert isinstance(a, A)
    assert isinstance(a.b, B)


@pytest.mark.parametrize(
    "method_name",
    ["add_transient_by_factory", "add_scoped_by_factory", "add_singleton_by_factory"],
)
def test_factories_activating_singleton_type_consistency(method_name):
    container = Container()

    class ABase(ABC):
        pass

    class BBase(ABC):
        pass

    @inject()
    class A(ABase):
        def __init__(self, b: BBase):
            self.b = b

    class B(BBase):
        def __init__(self):
            pass

    @inject()
    def bbase_factory(context: ActivationScope, activating_type: Type) -> BBase:
        assert isinstance(context, ActivationScope)
        assert activating_type is A
        return B()

    container.add_singleton(ABase, A)

    method = getattr(container, method_name)
    method(bbase_factory)

    provider = container.build_provider()
    context = ActivationScope(provider)

    a = provider.get(ABase, context)
    assert isinstance(a, A)
    assert isinstance(a.b, B)


@pytest.mark.parametrize(
    "method_name",
    ["add_transient_by_factory", "add_scoped_by_factory", "add_singleton_by_factory"],
)
def test_factories_type_transient_consistency_nested(method_name):
    container = Container()

    class ABase(ABC):
        pass

    class BBase(ABC):
        pass

    class CBase(ABC):
        pass

    @inject()
    class A(ABase):
        def __init__(self, b: BBase):
            self.b = b

    @inject()
    class B(BBase):
        def __init__(self, c: CBase):
            self.c = c

    class C(CBase):
        def __init__(self):
            pass

    @inject()
    def cbase_factory(context: ActivationScope, activating_type: Type) -> CBase:
        assert isinstance(context, ActivationScope)
        assert activating_type is B
        return C()

    container.add_transient(ABase, A)
    container.add_transient(BBase, B)

    method = getattr(container, method_name)
    method(cbase_factory)

    provider = container.build_provider()
    context = ActivationScope(provider)

    a = provider.get(ABase, context)
    assert isinstance(a, A)
    assert isinstance(a.b, B)
    assert isinstance(a.b.c, C)


@pytest.mark.parametrize(
    "method_name",
    ["add_transient_by_factory", "add_scoped_by_factory", "add_singleton_by_factory"],
)
def test_factories_type_scoped_consistency_nested(method_name):
    container = Container()

    class ABase(ABC):
        pass

    class BBase(ABC):
        pass

    class CBase(ABC):
        pass

    @inject()
    class A(ABase):
        def __init__(self, b: BBase):
            self.b = b

    @inject()
    class B(BBase):
        def __init__(self, c: CBase):
            self.c = c

    class C(CBase):
        def __init__(self):
            pass

    @inject()
    def cbase_factory(context: ActivationScope, activating_type: Type) -> CBase:
        assert isinstance(context, ActivationScope)
        assert activating_type is B
        return C()

    container.add_scoped(ABase, A)
    container.add_scoped(BBase, B)

    method = getattr(container, method_name)
    method(cbase_factory)

    provider = container.build_provider()
    context = ActivationScope(provider)

    a = provider.get(ABase, context)
    assert isinstance(a, A)
    assert isinstance(a.b, B)
    assert isinstance(a.b.c, C)


@pytest.mark.parametrize(
    "method_name",
    ["add_transient_by_factory", "add_scoped_by_factory", "add_singleton_by_factory"],
)
def test_factories_type_singleton_consistency_nested(method_name):
    container = Container()

    class ABase(ABC):
        pass

    class BBase(ABC):
        pass

    class CBase(ABC):
        pass

    @inject()
    class A(ABase):
        def __init__(self, b: BBase):
            self.b = b

    @inject()
    class B(BBase):
        def __init__(self, c: CBase):
            self.c = c

    class C(CBase):
        def __init__(self):
            pass

    @inject()
    def cbase_factory(context: ActivationScope, activating_type: Type) -> CBase:
        assert isinstance(context, ActivationScope)
        assert activating_type is B
        return C()

    container.add_singleton(ABase, A)
    container.add_singleton(BBase, B)

    method = getattr(container, method_name)
    method(cbase_factory)

    provider = container.build_provider()
    context = ActivationScope(provider)

    a = provider.get(ABase, context)
    assert isinstance(a, A)
    assert isinstance(a.b, B)
    assert isinstance(a.b.c, C)


def test_annotation_resolution():
    class B:
        pass

    @inject()
    class A:
        dep: B

    container = Container()

    b_singleton = B()
    container.add_instance(b_singleton)
    container._add_exact_scoped(A)

    provider = container.build_provider()

    instance = provider.get(A)

    assert isinstance(instance, A)
    assert instance.dep is not None
    assert instance.dep is b_singleton


def test_annotation_resolution_scoped():
    class B:
        pass

    @inject()
    class A:
        dep: B

    container = Container()

    b_singleton = B()
    container.add_instance(b_singleton)
    container._add_exact_scoped(A)

    provider = container.build_provider()

    with ActivationScope() as context:
        instance = provider.get(A, context)

        assert isinstance(instance, A)
        assert instance.dep is not None
        assert instance.dep is b_singleton

        second = provider.get(A, context)
        assert instance is second

    third = provider.get(A)
    assert third is not instance


def test_annotation_nested_resolution_1():
    class D:
        pass

    class C:
        pass

    @inject()
    class B:
        dep_1: C
        dep_2: D

    @inject()
    class A:
        dep: B

    container = Container()

    container.add_instance(C())
    container.add_instance(D())
    container._add_exact_transient(B)
    container._add_exact_scoped(A)

    provider = container.build_provider()

    with ActivationScope(provider) as context:
        instance = provider.get(A, context)

        assert isinstance(instance, A)
        assert isinstance(instance.dep, B)
        assert isinstance(instance.dep.dep_1, C)
        assert isinstance(instance.dep.dep_2, D)

        second = provider.get(A, context)
        assert instance is second

    third = provider.get(A)
    assert third is not instance


def test_annotation_nested_resolution_2():
    class E:
        pass

    @inject()
    class D:
        dep: E

    @inject()
    class C:
        dep: E

    @inject()
    class B:
        dep_1: C
        dep_2: D

    @inject()
    class A:
        dep: B

    container = Container()

    container.add_scoped_by_factory(E, E)
    container._add_exact_scoped(C)
    container._add_exact_scoped(D)
    container._add_exact_transient(B)
    container._add_exact_scoped(A)

    provider = container.build_provider()

    with ActivationScope(provider) as context:
        instance = provider.get(A, context)

        assert isinstance(instance, A)
        assert isinstance(instance.dep, B)
        assert isinstance(instance.dep.dep_1, C)
        assert isinstance(instance.dep.dep_2, D)
        assert isinstance(instance.dep.dep_1.dep, E)
        assert isinstance(instance.dep.dep_2.dep, E)
        assert instance.dep.dep_1.dep is instance.dep.dep_2.dep

        second = provider.get(A, context)
        assert instance is second
        assert instance.dep.dep_1.dep is second.dep.dep_1.dep

    third = provider.get(A)
    assert third is not instance


def test_annotation_resolution_singleton():
    class B:
        pass

    @inject()
    class A:
        dep: B

    container = Container()

    b_singleton = B()
    container.add_instance(b_singleton)
    container._add_exact_singleton(A)

    provider = container.build_provider()

    instance = provider.get(A)

    assert isinstance(instance, A)
    assert instance.dep is not None
    assert instance.dep is b_singleton

    second = provider.get(A)
    assert instance is second


def test_annotation_resolution_transient():
    class B:
        pass

    @inject()
    class A:
        dep: B

    container = Container()

    b_singleton = B()
    container.add_instance(b_singleton)
    container.add_transient(A)

    provider = container.build_provider()

    with ActivationScope() as context:
        instance = provider.get(A, context)

        assert isinstance(instance, A)
        assert instance.dep is not None
        assert instance.dep is b_singleton

        second = provider.get(A, context)
        assert instance is not second

        assert isinstance(second, A)
        assert second.dep is not None
        assert second.dep is b_singleton


def test_annotations_abstract_type_transient_service():
    class FooCatsRepository(ICatsRepository):
        def get_by_id(self, _id) -> Cat:
            return Cat("foo")

    class GetCatRequestHandler:
        cats_repository: ICatsRepository

        def get_cat(self, _id):
            cat = self.cats_repository.get_by_id(_id)
            return cat

    container = Container()
    container.add_transient(ICatsRepository, FooCatsRepository)
    container._add_exact_transient(GetCatRequestHandler)
    provider = container.build_provider()

    cats_repo = provider.get(ICatsRepository)
    assert isinstance(cats_repo, FooCatsRepository)

    other_cats_repo = provider.get(ICatsRepository)
    assert cats_repo is not other_cats_repo

    get_cat_handler = provider.get(GetCatRequestHandler)
    assert isinstance(get_cat_handler, GetCatRequestHandler)
    assert isinstance(get_cat_handler.cats_repository, FooCatsRepository)


def test_support_for_dataclasses():
    @dataclass
    class Settings:
        region: str

    @inject()
    @dataclass
    class GetInfoHandler:
        service_settings: Settings

        def handle_request(self):
            return {"service_region": self.service_settings.region}

    container = Container()
    container.add_instance(Settings(region="Western Europe"))
    container._add_exact_scoped(GetInfoHandler)

    provider = container.build_provider()

    info_handler = provider.get(GetInfoHandler)

    assert isinstance(info_handler, GetInfoHandler)
    assert isinstance(info_handler.service_settings, Settings)


def test_list():
    container = Container()

    class Foo:
        items: list

    container.add_instance(["one", "two", "three"])

    container._add_exact_scoped(Foo)

    provider = container.build_provider()

    instance = provider.get(Foo)

    assert instance.items == ["one", "two", "three"]


def test_list_generic_alias():
    container = Container()

    def list_int_factory() -> List[int]:
        return [1, 2, 3]

    def list_str_factory() -> List[str]:
        return ["a", "b"]

    class C:
        a: List[int]
        b: List[str]

    container.add_scoped_by_factory(list_int_factory)
    container.add_scoped_by_factory(list_str_factory)
    container.add_scoped(C)

    provider = container.build_provider()

    instance = provider.get(C)

    assert instance.a == list_int_factory()
    assert instance.b == list_str_factory()


def test_mapping_generic_alias():
    container = Container()

    def mapping_int_factory() -> Mapping[int, int]:
        return {1: 1, 2: 2, 3: 3}

    def mapping_str_factory() -> Mapping[str, int]:
        return {"a": 1, "b": 2, "c": 3}

    class C:
        a: Mapping[int, int]
        b: Mapping[str, int]

    container.add_scoped_by_factory(mapping_int_factory)
    container.add_scoped_by_factory(mapping_str_factory)
    container.add_scoped(C)

    provider = container.build_provider()

    instance = provider.get(C)

    assert instance.a == mapping_int_factory()
    assert instance.b == mapping_str_factory()


def test_dict_generic_alias():
    container = Container()

    def mapping_int_factory() -> Dict[int, int]:
        return {1: 1, 2: 2, 3: 3}

    def mapping_str_factory() -> Dict[str, int]:
        return {"a": 1, "b": 2, "c": 3}

    class C:
        a: Dict[int, int]
        b: Dict[str, int]

    container.add_scoped_by_factory(mapping_int_factory)
    container.add_scoped_by_factory(mapping_str_factory)
    container.add_scoped(C)

    provider = container.build_provider()

    instance = provider.get(C)

    assert instance.a == mapping_int_factory()
    assert instance.b == mapping_str_factory()


@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires Python 3.9")
def test_list_generic_alias_list():
    container = Container()

    def list_int_factory() -> list[int]:
        return [1, 2, 3]

    def list_str_factory() -> list[str]:
        return ["a", "b"]

    class C:
        a: list[int]
        b: list[str]

    container.add_scoped_by_factory(list_int_factory)
    container.add_scoped_by_factory(list_str_factory)
    container.add_scoped(C)

    provider = container.build_provider()

    instance = provider.get(C)

    assert instance.a == list_int_factory()
    assert instance.b == list_str_factory()


@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires Python 3.9")
def test_dict_generic_alias_dict():
    container = Container()

    def mapping_int_factory() -> dict[int, int]:
        return {1: 1, 2: 2, 3: 3}

    def mapping_str_factory() -> dict[str, int]:
        return {"a": 1, "b": 2, "c": 3}

    class C:
        a: dict[int, int]
        b: dict[str, int]

    container.add_scoped_by_factory(mapping_int_factory)
    container.add_scoped_by_factory(mapping_str_factory)
    container.add_scoped(C)

    provider = container.build_provider()

    instance = provider.get(C)

    assert instance.a == mapping_int_factory()
    assert instance.b == mapping_str_factory()


def test_generic():
    container = Container()

    class A(LoggedVar[int]):
        def __init__(self) -> None:
            super().__init__(10, "example")

    class B(LoggedVar[str]):
        def __init__(self) -> None:
            super().__init__("Foo", "example")

    class C:
        a: LoggedVar[int]
        b: LoggedVar[str]

    container.add_scoped(LoggedVar[int], A)
    container.add_scoped(LoggedVar[str], B)
    container.add_scoped(C)

    provider = container.build_provider()

    instance = provider.get(C)

    assert isinstance(instance.a, A)
    assert isinstance(instance.b, B)


ITERABLES = [
    (
        Iterable[LoggedVar[int]],
        [LoggedVar(1, "a"), LoggedVar(2, "b"), LoggedVar(3, "c")],
    ),
    (Iterable[str], ["one", "two", "three"]),
    (List[str], ["one", "two", "three"]),
    (Tuple[str, ...], ["one", "two", "three"]),
    (Sequence[str], ["one", "two", "three"]),
    (List[Cat], [Cat("A"), Cat("B"), Cat("C")]),
]


@pytest.mark.parametrize("annotation,value", ITERABLES)
def test_iterables_annotations_singleton(annotation, value):
    container = Container()

    @inject()
    class Foo:
        items: annotation

    container.add_instance(value, declared_class=annotation)

    container._add_exact_scoped(Foo)

    provider = container.build_provider()

    instance = provider.get(Foo)

    assert instance.items == value


@pytest.mark.parametrize("annotation,value", ITERABLES)
def test_iterables_annotations_scoped_factory(annotation, value):
    container = Container()

    @inject()
    class Foo:
        items: annotation

    @inject()
    def factory() -> annotation:
        return value

    container.add_scoped_by_factory(factory).add_scoped(Foo)

    provider = container.build_provider()

    instance = provider.get(Foo)

    assert instance.items == value


@pytest.mark.parametrize("annotation,value", ITERABLES)
def test_iterables_annotations_transient_factory(annotation, value):
    container = Container()

    @inject()
    class Foo:
        items: annotation

    @inject()
    def factory() -> annotation:
        return value

    container.add_transient_by_factory(factory).add_scoped(Foo)

    provider = container.build_provider()

    instance = provider.get(Foo)

    assert instance.items == value


def test_factory_without_locals_raises():
    def factory_without_context() -> None:
        ...

    with pytest.raises(FactoryMissingContextException):
        _get_factory_annotations_or_throw(factory_without_context)


def test_factory_with_locals_get_annotations():
    @inject()
    def factory_without_context() -> "Cat":
        ...

    annotations = _get_factory_annotations_or_throw(factory_without_context)

    assert annotations["return"] is Cat


def test_deps_github_scenario():
    """
    CLAHandler
    ├── CommentsService --> GitHubCommentsAPI .
    └── ChecksService   --> GitHubChecksAPI   .
                                              ├── GitHubAuthHandler - GitHubSettings
                                              ├── GitHubAuthHandler - GitHubSettings
                                              └── HTTPClient
    """

    class HTTPClient:
        ...

    class CommentsService:
        ...

    class ChecksService:
        ...

    class CLAHandler:
        comments_service: CommentsService
        checks_service: ChecksService

    class GitHubSettings:
        ...

    class GitHubAuthHandler:
        settings: GitHubSettings
        http_client: HTTPClient

    class GitHubCommentsAPI(CommentsService):
        auth_handler: GitHubAuthHandler
        http_client: HTTPClient

    class GitHubChecksAPI(ChecksService):
        auth_handler: GitHubAuthHandler
        http_client: HTTPClient

    container = Container()

    container.add_singleton(HTTPClient)
    container.add_singleton(GitHubSettings)
    container.add_singleton(GitHubAuthHandler)
    container.add_singleton(CommentsService, GitHubCommentsAPI)
    container.add_singleton(ChecksService, GitHubChecksAPI)
    container.add_singleton(CLAHandler)

    provider = container.build_provider()

    cla_handler = provider.get(CLAHandler)
    assert isinstance(cla_handler, CLAHandler)
    assert isinstance(cla_handler.comments_service, GitHubCommentsAPI)
    assert isinstance(cla_handler.checks_service, GitHubChecksAPI)
    assert (
        cla_handler.comments_service.auth_handler
        is cla_handler.checks_service.auth_handler
    )


def test_container_protocol():
    container: ContainerProtocol = arrange_cats_example()

    class UsingAlias:
        def __init__(self, example):
            self.cats_controller = example

    container.register(UsingAlias)

    # arrange an exact alias for UsingAlias class init parameter:
    container.set_alias("example", CatsController)

    u = container.resolve(UsingAlias)

    assert isinstance(u, UsingAlias)
    assert isinstance(u.cats_controller, CatsController)
    assert isinstance(u.cats_controller.cat_request_handler, GetCatRequestHandler)


def test_container_protocol_register():
    container: ContainerProtocol = Container()

    class BaseA:
        pass

    class A(BaseA):
        pass

    container.register(BaseA, A)
    a = container.resolve(BaseA)

    assert isinstance(a, A)


def test_container_protocol_any_argument():
    container: ContainerProtocol = Container()

    class A:
        pass

    container.register(A, None, None, 1, noop="foo")
    a = container.resolve(A, None, None, 1, noop="foo")

    assert isinstance(a, A)


def test_container_register_instance():
    container: ContainerProtocol = Container()

    singleton = FooDBCatsRepository(FooDBContext(ServiceSettings("example")))

    container.register(ICatsRepository, instance=singleton)

    assert container.resolve(ICatsRepository) is singleton


def test_import_version():
    from rodi.__about__ import __version__  # noqa


def test_container_iter():
    container = Container()

    class A:
        pass

    class B:
        pass

    container.register(A)
    container.register(B)

    for key, value in container:
        assert key is A or key is B
        assert isinstance(value, DynamicResolver)


def test_provide_protocol_generic() -> None:
    T = TypeVar("T")

    class P(Protocol[T]):
        def foo(self, t: T) -> T:
            ...

    class A:
        ...

    class Impl(P[A]):
        def foo(self, t: A) -> A:
            return t

    container = Container()

    container.register(Impl)

    try:
        resolved = container.resolve(Impl)
    except CannotResolveParameterException as e:
        pytest.fail(str(e))

    assert isinstance(resolved, Impl)


def test_ignore_class_var():
    """
    ClassVar attributes must be ignored, because they are not instance attributes.
    """

    class A:
        foo: ClassVar[str] = "foo"

    class B:
        example: ClassVar[str] = "example"
        dependency: A

    container = Container()

    container.register(A)
    container.register(B)

    b = container.resolve(B)

    assert isinstance(b, B)
    assert b.example == "example"
    assert b.dependency.foo == "foo"


def test_ignore_subclass_class_var():
    """
    Class attributes must be ignored in implementations.
    """

    class A:
        foo = "foo"

    container = Container()

    container.register(A)

    a = container.resolve(A)

    assert a.foo == "foo"
