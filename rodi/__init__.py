import inspect
import re
import sys
from collections import defaultdict
from enum import Enum
from inspect import Signature, _empty, isabstract, isclass, iscoroutinefunction
from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
    get_type_hints,
)

AliasesTypeHint = Dict[str, Union[Type, str]]


T = TypeVar("T", covariant=True)


def inject(globalsns=None, localns=None) -> Callable[..., Any]:
    """
    Marks a class or a function as injected. This method is only necessary if the class
    uses locals and the user uses Python >= 3.10, to bind the function's locals to the
    factory.
    """
    if localns is None or globalsns is None:
        frame = inspect.currentframe()
        try:
            if localns is None:
                localns = frame.f_back.f_locals  # type: ignore
            if globalsns is None:
                globalsns = frame.f_back.f_globals  # type: ignore
        finally:
            del frame

    def decorator(f):
        f._locals = localns
        f._globals = globalsns
        return f

    return decorator


def _get_obj_locals(obj) -> Optional[Dict[str, Any]]:
    return getattr(obj, "_locals", None)


def class_name(input_type):
    if input_type in {list, set} and str(
        type(input_type) == "<class 'types.GenericAlias'>"
    ):
        # for Python 3.9 list[T], set[T]
        return str(input_type)
    try:
        return input_type.__name__
    except AttributeError:
        # for example, this is the case for List[str], Tuple[str, ...], etc.
        return str(input_type)


class DIException(Exception):
    """Base exception class for DI exceptions."""


class FactoryMissingContextException(DIException):
    def __init__(self, function) -> None:
        super().__init__(
            f"The factory '{function.__name__}' lacks locals and globals data. "
            "Decorate the function with the `@inject()` decorator defined in "
            "`rodi`. This is necessary since PEP 563."
        )


class CannotResolveTypeException(DIException):
    """
    Exception risen when it is not possible to resolve a Type."""

    def __init__(self, desired_type):
        super().__init__(f"Unable to resolve the type '{desired_type}'.")


class CannotResolveParameterException(DIException):
    """
    Exception risen when it is not possible to resolve a parameter,
    necessary to instantiate a type."""

    def __init__(self, param_name, desired_type):
        super().__init__(
            f"Unable to resolve parameter '{param_name}' "
            f"when resolving '{class_name(desired_type)}'"
        )


class UnsupportedUnionTypeException(DIException):
    """Exception risen when a parameter type is defined
    as Optional or Union of several types."""

    def __init__(self, param_name, desired_type):
        super().__init__(
            f"Union or Optional type declaration is not supported. "
            f"Cannot resolve parameter '{param_name}' "
            f"when resolving '{class_name(desired_type)}'"
        )


class OverridingServiceException(DIException):
    """
    Exception risen when registering a service
    would override an existing one."""

    def __init__(self, key, value):
        key_name = key if isinstance(key, str) else class_name(key)
        super().__init__(
            f"A service with key '{key_name}' is already "
            f"registered and would be overridden by value {value}."
        )


class CircularDependencyException(DIException, RecursionError):
    """Exception risen when a circular dependency between a type and
    one of its parameters is detected."""

    def __init__(self, expected_type, desired_type):
        super().__init__(
            "A circular dependency was detected for the service "
            f"of type '{class_name(expected_type)}' "
            f"for '{class_name(desired_type)}'"
        )


class InvalidOperationInStrictMode(DIException):
    def __init__(self):
        super().__init__(
            "The services are configured in strict mode, the operation is invalid."
        )


class AliasAlreadyDefined(DIException):
    """Exception risen when trying to add an alias that already exists."""

    def __init__(self, name):
        super().__init__(
            f"Cannot define alias '{name}'. "
            f"An alias with given name is already defined."
        )


class AliasConfigurationError(DIException):
    def __init__(self, name, _type):
        super().__init__(
            f"An alias '{name}' for type '{class_name(_type)}' was defined, "
            f"but the type was not configured in the Container."
        )


class MissingTypeException(DIException):
    """Exception risen when a type must be specified to use a factory"""

    def __init__(self):
        super().__init__(
            "Please specify the factory return type or "
            "annotate its return type; func() -> Foo:"
        )


class InvalidFactory(DIException):
    """Exception risen when a factory is not valid"""

    def __init__(self, _type):
        super().__init__(
            f"The factory specified for type {class_name(_type)} is not "
            f"valid, it must be a function with either these signatures: "
            f"def example_factory(context, type): "
            f"or,"
            f"def example_factory(context): "
            f"or,"
            f"def example_factory(): "
        )


class ServiceLifeStyle(Enum):
    TRANSIENT = 1
    SCOPED = 2
    SINGLETON = 3


def _get_factory_annotations_or_throw(factory):
    factory_locals = getattr(factory, "_locals", None)
    factory_globals = getattr(factory, "_globals", None)

    if factory_locals is None:
        raise FactoryMissingContextException(factory)

    return get_type_hints(factory, globalns=factory_globals, localns=factory_locals)


class GetServiceContext:
    __slots__ = ("scoped_services", "provider", "types_chain")

    def __init__(self, provider=None, scoped_services=None):
        self.provider = provider
        self.scoped_services = scoped_services or {}

    def __enter__(self):
        if self.scoped_services is None:
            self.scoped_services = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

    def dispose(self):
        if self.provider:
            self.provider = None

        if self.scoped_services:
            self.scoped_services.clear()
            self.scoped_services = None


class ResolveContext:
    __slots__ = ("resolved", "dynamic_chain")

    def __init__(self):
        self.resolved = {}
        self.dynamic_chain = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

    def dispose(self):
        del self.resolved
        self.dynamic_chain.clear()


class InstanceProvider:
    __slots__ = ("instance",)

    def __init__(self, instance):
        self.instance = instance

    def __call__(self, context, parent_type):
        return self.instance


class TypeProvider:
    __slots__ = ("_type",)

    def __init__(self, _type):
        self._type = _type

    def __call__(self, context, parent_type):
        return self._type()


class ScopedTypeProvider:
    __slots__ = ("_type",)

    def __init__(self, _type):
        self._type = _type

    def __call__(self, context: GetServiceContext, parent_type):
        if self._type in context.scoped_services:
            return context.scoped_services[self._type]

        service = self._type()
        context.scoped_services[self._type] = service
        return service


class ArgsTypeProvider:
    __slots__ = ("_type", "_args_callbacks")

    def __init__(self, _type, args_callbacks):
        self._type = _type
        self._args_callbacks = args_callbacks

    def __call__(self, context, parent_type):
        return self._type(*[fn(context, self._type) for fn in self._args_callbacks])


class FactoryTypeProvider:
    __slots__ = ("_type", "factory")

    def __init__(self, _type, factory):
        self._type = _type
        self.factory = factory

    def __call__(self, context: GetServiceContext, parent_type):
        assert isinstance(context, GetServiceContext)
        return self.factory(context, parent_type)


class SingletonFactoryTypeProvider:
    __slots__ = ("_type", "factory", "instance")

    def __init__(self, _type, factory):
        self._type = _type
        self.factory = factory
        self.instance = None

    def __call__(self, context: GetServiceContext, parent_type):
        if self.instance is None:
            self.instance = self.factory(context, parent_type)
        return self.instance


class ScopedFactoryTypeProvider:
    __slots__ = ("_type", "factory")

    def __init__(self, _type, factory):
        self._type = _type
        self.factory = factory

    def __call__(self, context: GetServiceContext, parent_type):
        if self._type in context.scoped_services:
            return context.scoped_services[self._type]

        instance = self.factory(context, parent_type)
        context.scoped_services[self._type] = instance
        return instance


class ScopedArgsTypeProvider:
    __slots__ = ("_type", "_args_callbacks")

    def __init__(self, _type, args_callbacks):
        self._type = _type
        self._args_callbacks = args_callbacks

    def __call__(self, context: GetServiceContext, parent_type):
        if self._type in context.scoped_services:
            return context.scoped_services[self._type]

        service = self._type(*[fn(context, self._type) for fn in self._args_callbacks])
        context.scoped_services[self._type] = service
        return service


class SingletonTypeProvider:
    __slots__ = ("_type", "_instance", "_args_callbacks")

    def __init__(self, _type, _args_callbacks):
        self._type = _type
        self._args_callbacks = _args_callbacks
        self._instance = None

    def __call__(self, context, parent_type):
        if not self._instance:
            self._instance = (
                self._type(*[fn(context, self._type) for fn in self._args_callbacks])
                if self._args_callbacks
                else self._type()
            )

        return self._instance


def get_annotations_type_provider(
    concrete_type: Type,
    resolvers: Mapping[str, Callable],
    life_style: ServiceLifeStyle,
    resolver_context: ResolveContext,
):
    def factory(context, parent_type):
        instance = concrete_type()
        for name, resolver in resolvers.items():
            setattr(instance, name, resolver(context, parent_type))
        return instance

    return FactoryResolver(concrete_type, factory, life_style)(resolver_context)


def _get_plain_class_factory(concrete_type: Type):
    def factory(*args):
        return concrete_type()

    return factory


class InstanceResolver:
    __slots__ = ("instance",)

    def __init__(self, instance):
        self.instance = instance

    def __repr__(self):
        return f"<Singleton {class_name(self.instance.__class__)}>"

    def __call__(self, context: ResolveContext):
        return InstanceProvider(self.instance)


class Dependency:
    __slots__ = ("name", "annotation")

    def __init__(self, name, annotation):
        self.name = name
        self.annotation = annotation


class DynamicResolver:
    __slots__ = ("_concrete_type", "services", "life_style")

    def __init__(self, concrete_type, services, life_style):
        assert isclass(concrete_type)
        assert not isabstract(concrete_type)

        self._concrete_type = concrete_type
        self.services = services
        self.life_style = life_style

    @property
    def concrete_type(self):
        return self._concrete_type

    def _get_resolver(self, desired_type, context: ResolveContext):
        # NB: the following two lines are important to ensure that singletons
        # are instantiated only once per service provider
        # to not repeat operations more than once
        if desired_type in context.resolved:
            return context.resolved[desired_type]

        reg = self.services._map.get(desired_type)
        assert reg is not None, (
            f"A resolver for type {class_name(desired_type)} " f"is not configured"
        )
        return reg(context)

    def _get_resolvers_for_parameters(
        self,
        concrete_type,
        context: ResolveContext,
        params: Mapping[str, Dependency],
    ):
        fns = []
        services = self.services

        for param_name, param in params.items():
            if param_name == "self":
                continue

            param_type = param.annotation

            if hasattr(param_type, "__origin__") and param_type.__origin__ is Union:
                # NB: we could cycle through possible types using: param_type.__args__
                # Right now Union and Optional types resolution is not implemented,
                # but at least Optional could be supported in the future
                raise UnsupportedUnionTypeException(param_name, concrete_type)

            if param_type is _empty:
                if services.strict:
                    raise CannotResolveParameterException(param_name, concrete_type)

                # support for exact, user defined aliases, without ambiguity
                exact_alias = services._exact_aliases.get(param_name)

                if exact_alias:
                    param_type = exact_alias
                else:
                    aliases = services._aliases[param_name]

                    if aliases:
                        assert (
                            len(aliases) == 1
                        ), "Configured aliases cannot be ambiguous"
                        for param_type in aliases:
                            break

            if param_type not in services._map:
                raise CannotResolveParameterException(param_name, concrete_type)

            param_resolver = self._get_resolver(param_type, context)
            fns.append(param_resolver)
        return fns

    def _resolve_by_init_method(self, context: ResolveContext):
        sig = Signature.from_callable(self.concrete_type.__init__)
        params = {
            key: Dependency(key, value.annotation)
            for key, value in sig.parameters.items()
        }

        if sys.version_info >= (3, 10):  # pragma: no cover
            # Python 3.10
            annotations = get_type_hints(
                self.concrete_type.__init__,
                vars(sys.modules[self.concrete_type.__module__]),
                _get_obj_locals(self.concrete_type),
            )
            for key, value in params.items():
                if key in annotations:
                    value.annotation = annotations[key]

        concrete_type = self.concrete_type

        if len(params) == 1 and next(iter(params.keys())) == "self":
            if self.life_style == ServiceLifeStyle.SINGLETON:
                return SingletonTypeProvider(concrete_type, None)

            if self.life_style == ServiceLifeStyle.SCOPED:
                return ScopedTypeProvider(concrete_type)

            return TypeProvider(concrete_type)

        fns = self._get_resolvers_for_parameters(concrete_type, context, params)

        if self.life_style == ServiceLifeStyle.SINGLETON:
            return SingletonTypeProvider(concrete_type, fns)

        if self.life_style == ServiceLifeStyle.SCOPED:
            return ScopedArgsTypeProvider(concrete_type, fns)

        return ArgsTypeProvider(concrete_type, fns)

    def _resolve_by_annotations(
        self, context: ResolveContext, annotations: Dict[str, Type]
    ):
        params = {key: Dependency(key, value) for key, value in annotations.items()}
        concrete_type = self.concrete_type

        fns = self._get_resolvers_for_parameters(concrete_type, context, params)
        resolvers = {}

        i = 0
        for name in annotations.keys():
            resolvers[name] = fns[i]
            i += 1

        return get_annotations_type_provider(
            self.concrete_type, resolvers, self.life_style, context
        )

    def __call__(self, context: ResolveContext):
        concrete_type = self.concrete_type

        chain = context.dynamic_chain
        chain.append(concrete_type)

        if getattr(concrete_type, "__init__") is object.__init__:
            annotations = get_type_hints(
                concrete_type,
                vars(sys.modules[concrete_type.__module__]),
                _get_obj_locals(concrete_type),
            )

            if annotations:
                try:
                    return self._resolve_by_annotations(context, annotations)
                except RecursionError:
                    raise CircularDependencyException(chain[0], concrete_type)

            return FactoryResolver(
                concrete_type, _get_plain_class_factory(concrete_type), self.life_style
            )(context)

        try:
            return self._resolve_by_init_method(context)
        except RecursionError:
            raise CircularDependencyException(chain[0], concrete_type)


class FactoryResolver:
    __slots__ = ("concrete_type", "factory", "params", "life_style")

    def __init__(self, concrete_type, factory, life_style):
        self.factory = factory
        self.concrete_type = concrete_type
        self.life_style = life_style

    def __call__(self, context: ResolveContext):
        if self.life_style == ServiceLifeStyle.SINGLETON:
            return SingletonFactoryTypeProvider(self.concrete_type, self.factory)

        if self.life_style == ServiceLifeStyle.SCOPED:
            return ScopedFactoryTypeProvider(self.concrete_type, self.factory)

        return FactoryTypeProvider(self.concrete_type, self.factory)


first_cap_re = re.compile("(.)([A-Z][a-z]+)")
all_cap_re = re.compile("([a-z0-9])([A-Z])")


def to_standard_param_name(name):
    value = all_cap_re.sub(r"\1_\2", first_cap_re.sub(r"\1_\2", name)).lower()
    if value.startswith("i_"):
        return "i" + value[2:]
    return value


class Services:
    """
    Provides methods to activate instances of classes,
    by cached activator functions.
    """

    __slots__ = ("_map", "_executors")

    def __init__(self, services_map=None):
        if services_map is None:
            services_map = {}
        self._map = services_map
        self._executors = {}

    def __contains__(self, item):
        return item in self._map

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        self.set(key, value)

    def set(self, new_type: Union[Type, str], value: Any):
        """
        Sets a new service of desired type, as singleton.
        This method exists to increase interoperability of Services class (with dict).

        :param new_type:
        :param value:
        :return:
        """
        type_name = class_name(new_type)
        if new_type in self._map or (
            not isinstance(new_type, str) and type_name in self._map
        ):
            raise OverridingServiceException(self._map[new_type], new_type)

        def resolver(context, desired_type):
            return value

        self._map[new_type] = resolver
        if not isinstance(new_type, str):
            self._map[type_name] = resolver

    def get(
        self,
        desired_type: Union[Type[T], str],
        context: Optional[GetServiceContext] = None,
        *,
        default: Optional[Any] = ...,
    ) -> T:
        """
        Gets a service of the desired type, returning an activated instance.

        :param desired_type: desired service type.
        :param context: optional context, used to handle scoped services.
        :return: an instance of the desired type
        """
        if context is None:
            context = GetServiceContext(self)

        resolver = self._map.get(desired_type)

        if not resolver:
            if default is not ...:
                return cast(T, default)
            raise CannotResolveTypeException(desired_type)

        return cast(T, resolver(context, desired_type))

    def _get_getter(self, key, param):
        if param.annotation is _empty:

            def getter(context):
                return self.get(key, context)

        else:

            def getter(context):
                return self.get(param.annotation, context)

        getter.__name__ = f"<getter {key}>"
        return getter

    def get_executor(self, method: Callable) -> Callable:
        sig = Signature.from_callable(method)
        params = {
            key: Dependency(key, value.annotation)
            for key, value in sig.parameters.items()
        }

        if sys.version_info >= (3, 10):  # pragma: no cover
            # Python 3.10
            annotations = _get_factory_annotations_or_throw(method)
            for key, value in params.items():
                if key in annotations:
                    value.annotation = annotations[key]

        fns = []

        for key, value in params.items():
            fns.append(self._get_getter(key, value))

        if iscoroutinefunction(method):

            async def async_executor(scoped: Optional[Dict[Type, Any]] = None):
                with GetServiceContext(self, scoped) as context:
                    return await method(*[fn(context) for fn in fns])

            return async_executor

        def executor(scoped: Optional[Dict[Type, Any]] = None):
            with GetServiceContext(self, scoped) as context:
                return method(*[fn(context) for fn in fns])

        return executor

    def exec(
        self,
        method: Callable,
        scoped: Optional[Dict[Type, Any]] = None,
    ) -> Any:
        try:
            executor = self._executors[method]
        except KeyError:
            executor = self.get_executor(method)
            self._executors[method] = executor
        return executor(scoped)


FactoryCallableNoArguments = Callable[[], Any]
FactoryCallableSingleArgument = Callable[[GetServiceContext], Any]
FactoryCallableTwoArguments = Callable[[GetServiceContext, Type], Any]
FactoryCallableType = Union[
    FactoryCallableNoArguments,
    FactoryCallableSingleArgument,
    FactoryCallableTwoArguments,
]


class FactoryWrapperNoArgs:

    __slots__ = ("factory",)

    def __init__(self, factory):
        self.factory = factory

    def __call__(self, context, activating_type):
        return self.factory()


class FactoryWrapperContextArg:
    __slots__ = ("factory",)

    def __init__(self, factory):
        self.factory = factory

    def __call__(self, context, activating_type):
        return self.factory(context)


class Container:
    """
    Configuration class for a collection of services."""

    __slots__ = ("_map", "_aliases", "_exact_aliases", "strict")

    def __init__(self, strict: bool = False):
        self._map = {}
        self._aliases = None if strict else defaultdict(set)
        self._exact_aliases = None if strict else {}
        self.strict = strict

    def __contains__(self, key):
        return key in self._map

    def register(
        self, base_type: Type, concrete_type: Type, life_style: ServiceLifeStyle
    ):
        try:
            assert issubclass(concrete_type, base_type), (
                f"Cannot register {class_name(base_type)} for abstract class "
                f"{class_name(concrete_type)}"
            )
        except TypeError:
            # ignore, this happens with generic types
            pass

        self._bind(base_type, DynamicResolver(concrete_type, self, life_style))
        return self

    def add_alias(self, name: str, desired_type: Type):
        """
        Adds an alias to the set of inferred aliases.

        :param name: parameter name
        :param desired_type: desired type by parameter name
        :return: self
        """
        if self.strict:
            raise InvalidOperationInStrictMode()
        if name in self._aliases or name in self._exact_aliases:
            raise AliasAlreadyDefined(name)
        self._aliases[name].add(desired_type)
        return self

    def add_aliases(self, values: AliasesTypeHint):
        """
        Adds aliases to the set of inferred aliases.

        :param values: mapping object (parameter name: class)
        :return: self
        """
        for key, value in values.items():
            self.add_alias(key, value)
        return self

    def set_alias(self, name: str, desired_type: Type, override: bool = False):
        """
        Sets an exact alias for a desired type.

        :param name: parameter name
        :param desired_type: desired type by parameter name
        :param override: whether to override existing values, or throw exception
        :return: self
        """
        if self.strict:
            raise InvalidOperationInStrictMode()
        if not override and name in self._exact_aliases:
            raise AliasAlreadyDefined(name)
        self._exact_aliases[name] = desired_type
        return self

    def set_aliases(self, values: AliasesTypeHint, override: bool = False):
        """Sets many exact aliases for desired types.

        :param values: mapping object (parameter name: class)
        :param override: whether to override existing values, or throw exception
        :return: self
        """
        for key, value in values.items():
            self.set_alias(key, value, override)
        return self

    def _bind(self, key: Type, value: Any) -> None:
        if key in self._map:
            raise OverridingServiceException(key, value)
        self._map[key] = value

        key_name = class_name(key)

        if self.strict or "." in key_name:
            return

        self._aliases[key_name].add(key)
        self._aliases[key_name.lower()].add(key)
        self._aliases[to_standard_param_name(key_name)].add(key)

    def add_instance(
        self, instance: Any, declared_class: Optional[Type] = None
    ) -> "Container":
        """
        Registers an exact instance, optionally by declared class.

        :param instance: singleton to be registered
        :param declared_class: optionally, lets define the class used as reference of
        the singleton
        :return: the service collection itself
        """
        self._bind(
            instance.__class__ if not declared_class else declared_class,
            InstanceResolver(instance),
        )
        return self

    def add_singleton(
        self, base_type: Type, concrete_type: Optional[Type] = None
    ) -> "Container":
        """
        Registers a type by base type, to be instantiated with singleton lifetime.
        If a single type is given, the method `add_exact_singleton` is used.

        :param base_type: registered type. If a concrete type is provided, it must
        inherit the base type.
        :param concrete_type: concrete class
        :return: the service collection itself
        """
        if concrete_type is None:
            return self.add_exact_singleton(base_type)

        return self.register(base_type, concrete_type, ServiceLifeStyle.SINGLETON)

    def add_scoped(
        self, base_type: Type, concrete_type: Optional[Type] = None
    ) -> "Container":
        """
        Registers a type by base type, to be instantiated with scoped lifetime.
        If a single type is given, the method `add_exact_scoped` is used.

        :param base_type: registered type. If a concrete type is provided, it must
        inherit the base type.
        :param concrete_type: concrete class
        :return: the service collection itself
        """
        if concrete_type is None:
            return self.add_exact_scoped(base_type)

        return self.register(base_type, concrete_type, ServiceLifeStyle.SCOPED)

    def add_transient(
        self, base_type: Type, concrete_type: Optional[Type] = None
    ) -> "Container":
        """
        Registers a type by base type, to be instantiated with transient lifetime.
        If a single type is given, the method `add_exact_transient` is used.

        :param base_type: registered type. If a concrete type is provided, it must
        inherit the base type.
        :param concrete_type: concrete class
        :return: the service collection itself
        """
        if concrete_type is None:
            return self.add_exact_transient(base_type)

        return self.register(base_type, concrete_type, ServiceLifeStyle.TRANSIENT)

    def add_exact_singleton(self, concrete_type: Type) -> "Container":
        """
        Registers an exact type, to be instantiated with singleton lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        assert not isabstract(concrete_type)
        self._bind(
            concrete_type,
            DynamicResolver(concrete_type, self, ServiceLifeStyle.SINGLETON),
        )
        return self

    def add_exact_scoped(self, concrete_type: Type) -> "Container":
        """
        Registers an exact type, to be instantiated with scoped lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        assert not isabstract(concrete_type)
        self._bind(
            concrete_type, DynamicResolver(concrete_type, self, ServiceLifeStyle.SCOPED)
        )
        return self

    def add_exact_transient(self, concrete_type: Type) -> "Container":
        """
        Registers an exact type, to be instantiated with transient lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        assert not isabstract(concrete_type)
        self._bind(
            concrete_type,
            DynamicResolver(concrete_type, self, ServiceLifeStyle.TRANSIENT),
        )
        return self

    def add_singleton_by_factory(
        self, factory: FactoryCallableType, return_type: Optional[Type] = None
    ) -> "Container":
        self.register_factory(factory, return_type, ServiceLifeStyle.SINGLETON)
        return self

    def add_transient_by_factory(
        self, factory: FactoryCallableType, return_type: Optional[Type] = None
    ) -> "Container":
        self.register_factory(factory, return_type, ServiceLifeStyle.TRANSIENT)
        return self

    def add_scoped_by_factory(
        self, factory: FactoryCallableType, return_type: Optional[Type] = None
    ) -> "Container":
        self.register_factory(factory, return_type, ServiceLifeStyle.SCOPED)
        return self

    def _check_factory(self, factory, signature, handled_type) -> None:
        assert callable(factory), "The factory must be callable"

        params_len = len(signature.parameters)

        if params_len == 0:
            return FactoryWrapperNoArgs(factory)

        if params_len == 1:
            return FactoryWrapperContextArg(factory)

        if params_len == 2:
            return factory

        raise InvalidFactory(handled_type)

    def register_factory(
        self,
        factory: Callable,
        return_type: Optional[Type],
        life_style: ServiceLifeStyle,
    ) -> None:
        if not callable(factory):
            raise InvalidFactory(return_type)

        sign = Signature.from_callable(factory)
        if return_type is None:
            if sign.return_annotation is _empty:
                raise MissingTypeException()
            return_type = sign.return_annotation

            if isinstance(return_type, str):  # pragma: no cover
                # Python 3.10
                annotations = _get_factory_annotations_or_throw(factory)
                return_type = annotations["return"]

        self._bind(
            return_type,
            FactoryResolver(
                return_type, self._check_factory(factory, sign, return_type), life_style
            ),
        )

    def build_provider(self) -> Services:
        """
        Builds and returns a service provider that can be used to activate and
        obtain services.

        The configuration of services is validated at this point, if any service cannot
        be instantiated due to missing dependencies, an exception is thrown inside this
        operation.

        :return: Service provider that can be used to activate and obtain services.
        """
        with ResolveContext() as context:
            _map = {}

            for _type, resolver in self._map.items():
                # NB: do not call resolver if one was already prepared for the type
                assert _type not in context.resolved, "_map keys must be unique"

                if isinstance(resolver, DynamicResolver):
                    context.dynamic_chain.clear()

                _map[_type] = resolver(context)
                context.resolved[_type] = _map[_type]

                type_name = class_name(_type)
                if "." not in type_name:
                    _map[type_name] = _map[_type]

            if not self.strict:
                assert self._aliases is not None
                assert self._exact_aliases is not None

                # include aliases in the map;
                for name, _types in self._aliases.items():
                    for _type in _types:
                        break
                    _map[name] = self._get_alias_target_type(name, _map, _type)

                for name, _type in self._exact_aliases.items():
                    _map[name] = self._get_alias_target_type(name, _map, _type)

        return Services(_map)

    @staticmethod
    def _get_alias_target_type(name, _map, _type):
        try:
            return _map[_type]
        except KeyError:
            raise AliasConfigurationError(name, _type)
