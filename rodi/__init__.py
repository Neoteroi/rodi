import contextvars
import inspect
import re
import sys
from collections import defaultdict
from enum import Enum
from inspect import Signature, _empty, isabstract, isclass, iscoroutinefunction
from typing import (
    Any,
    Callable,
    ClassVar,
    DefaultDict,
    Iterator,
    Mapping,
    Protocol,
    Type,
    TypeVar,
)
from typing import _no_init_or_replace_init as _no_init
from typing import (
    cast,
    get_type_hints,
    overload,
)

T = TypeVar("T")


class ContainerProtocol(Protocol):
    """
    Generic interface of DI Container that can register and resolve services,
    and tell if a type is configured.
    """

    def register(self, obj_type: Type | str, *args, **kwargs) -> None:
        """Registers a type in the container, with optional arguments."""

    @overload
    def resolve(self, obj_type: Type[T], *args, **kwargs) -> T: ...

    @overload
    def resolve(self, obj_type: str, *args, **kwargs) -> Any: ...

    def resolve(self, obj_type: Type[T] | str, *args, **kwargs) -> Any:
        """Activates an instance of the given type, with optional arguments."""

    def __contains__(self, item) -> bool:
        """
        Returns a value indicating whether a given type is configured in this container.
        """


AliasesTypeHint = dict[str, Type]


def inject(
    globalsns: dict[str, Any] | None = None,
    localns: dict[str, Any] | None = None,
) -> Callable[[T], T]:
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


def _get_obj_locals(obj) -> dict[str, Any] | None:
    return getattr(obj, "_locals", None)


def _get_obj_globals(obj) -> dict[str, Any]:
    return getattr(obj, "_globals", {})


def class_name(input_type):
    if input_type in {list, set} and str(  # noqa: E721
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


class CircularDependencyException(DIException):
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


class DecoratorRegistrationException(DIException):
    """
    Exception raised when registering a decorator fails, either because the base type
    is not registered or because the decorator class has no parameter matching the
    base type.
    """

    def __init__(self, base_type, decorator_type):
        if decorator_type is None:
            super().__init__(
                f"Cannot register a decorator for type '{class_name(base_type)}': "
                f"the type is not registered in the container."
            )
        else:
            super().__init__(
                f"Cannot register '{class_name(decorator_type)}' as a decorator for "
                f"'{class_name(base_type)}': no __init__ parameter with a type "
                f"annotation matching '{class_name(base_type)}' was found."
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


class ActivationScope:
    __slots__ = ("scoped_services", "provider")

    def __init__(
        self,
        provider: "Services | None" = None,
        scoped_services: dict[Type[T] | str, T] | None = None,
    ):
        self.provider = provider or Services()
        self.scoped_services = scoped_services or {}

    def __enter__(self):
        if self.scoped_services is None:
            self.scoped_services = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

    def get(
        self,
        desired_type: Type[T] | str,
        scope: "ActivationScope | None" = None,
        *,
        default: Any = ...,
    ) -> T:
        if self.provider is None:
            raise TypeError("This scope is disposed.")
        return self.provider.get(desired_type, scope or self, default=default)

    def dispose(self):
        if self.provider:
            self.provider = None

        if self.scoped_services:
            self.scoped_services.clear()
            self.scoped_services = None


class TrackingActivationScope(ActivationScope):
    """
    This is an experimental class to support nested scopes transparently.
    To use it, create a container including the `scope_cls` parameter:
    `Container(scope_cls=TrackingActivationScope)`.
    """

    _active_scopes = contextvars.ContextVar("active_scopes", default=[])

    __slots__ = ("scoped_services", "provider", "parent_scope")

    def __init__(self, provider=None, scoped_services=None):
        # Get the current stack of active scopes
        stack = self._active_scopes.get()

        # Detect the parent scope if it exists
        self.parent_scope = stack[-1] if stack else None

        # Initialize scoped services
        scoped_services = scoped_services or {}
        if self.parent_scope:
            scoped_services.update(self.parent_scope.scoped_services)

        super().__init__(provider, scoped_services)

    def __enter__(self):
        # Push this scope onto the stack
        stack = self._active_scopes.get()
        self._active_scopes.set(stack + [self])
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Pop this scope from the stack
        stack = self._active_scopes.get()
        self._active_scopes.set(stack[:-1])
        self.dispose()

    def dispose(self):
        if self.provider:
            self.provider = None


class ResolutionContext:
    __slots__ = ("resolved", "dynamic_chain")
    __deletable__ = ("resolved",)

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

    def __call__(self, context: ActivationScope, parent_type):
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

    def __call__(self, context: ActivationScope, parent_type):
        assert isinstance(context, ActivationScope)
        return self.factory(context, parent_type)


class SingletonFactoryTypeProvider:
    __slots__ = ("_type", "factory", "instance")

    def __init__(self, _type, factory):
        self._type = _type
        self.factory = factory
        self.instance = None

    def __call__(self, context: ActivationScope, parent_type):
        if self.instance is None:
            self.instance = self.factory(context, parent_type)
        return self.instance


class ScopedFactoryTypeProvider:
    __slots__ = ("_type", "factory")

    def __init__(self, _type, factory):
        self._type = _type
        self.factory = factory

    def __call__(self, context: ActivationScope, parent_type):
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

    def __call__(self, context: ActivationScope, parent_type):
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
        if self._instance is None:
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
    resolver_context: ResolutionContext,
):
    def factory(context, parent_type):
        instance = concrete_type()
        for name, resolver in resolvers.items():
            setattr(instance, name, resolver(context, parent_type))
        return instance

    return FactoryResolver(concrete_type, factory, life_style)(resolver_context)


def get_mixed_type_provider(
    concrete_type: Type,
    args_callbacks: list,
    annotation_resolvers: Mapping[str, Callable],
    life_style: ServiceLifeStyle,
    resolver_context: ResolutionContext,
):
    """
    Provider that combines __init__ argument injection with class-level annotation
    property injection. Used when a class defines both a custom __init__ (with or
    without parameters) and class-level annotated attributes.
    """

    def factory(context, parent_type):
        instance = concrete_type(*[fn(context, parent_type) for fn in args_callbacks])
        for name, resolver in annotation_resolvers.items():
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

    def __call__(self, context: ResolutionContext):
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
    def concrete_type(self) -> Type:
        return self._concrete_type

    def _get_resolver(self, desired_type, context: ResolutionContext):
        # NB: the following two lines are important to ensure that singletons
        # are instantiated only once per service provider
        # to not repeat operations more than once
        if desired_type in context.resolved:
            return context.resolved[desired_type]

        reg = self.services._map.get(desired_type)
        assert (
            reg is not None
        ), f"A resolver for type {class_name(desired_type)} is not configured"
        resolver = reg(context)

        # add the resolver to the context, so we can find it
        # next time we need it
        context.resolved[desired_type] = resolver
        return resolver

    def _get_resolvers_for_parameters(
        self,
        concrete_type,
        context: ResolutionContext,
        params: Mapping[str, Dependency],
    ):
        fns = []
        services = self.services

        for param_name, param in params.items():
            if param_name in ("self", "args", "kwargs"):
                continue

            param_type = param.annotation

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

    def _resolve_by_init_method(self, context: ResolutionContext):
        sig = Signature.from_callable(self.concrete_type.__init__)
        params = {
            key: Dependency(key, value.annotation)
            for key, value in sig.parameters.items()
        }

        globalns = dict(vars(sys.modules[self.concrete_type.__module__]))
        globalns.update(_get_obj_globals(self.concrete_type))
        annotations = get_type_hints(
            self.concrete_type.__init__,
            globalns,
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

    def _ignore_class_attribute(self, key: str, value) -> bool:
        """
        Returns a value indicating whether a class attribute should be ignored for
        dependency resolution, by name and value.
        It's ignored if it's a ClassVar or if it's already initialized explicitly.
        """
        is_classvar = getattr(value, "__origin__", None) is ClassVar
        is_initialized = getattr(self.concrete_type, key, None) is not None

        return is_classvar or is_initialized

    def _has_default_init(self):
        init = getattr(self.concrete_type, "__init__", None)

        if init is object.__init__:
            return True

        if init is _no_init:
            return True
        return False

    def _resolve_by_annotations(
        self, context: ResolutionContext, annotations: dict[str, Type]
    ):
        params = {
            key: Dependency(key, value)
            for key, value in annotations.items()
            if not self._ignore_class_attribute(key, value)
        }
        concrete_type = self.concrete_type

        fns = self._get_resolvers_for_parameters(concrete_type, context, params)
        resolvers = {}

        for i, name in enumerate(params.keys()):
            resolvers[name] = fns[i]

        return get_annotations_type_provider(
            self.concrete_type, resolvers, self.life_style, context
        )

    def _resolve_by_init_and_annotations(
        self, context: ResolutionContext, extra_annotations: dict[str, Type]
    ):
        """
        Resolves by both __init__ parameters and class-level annotated properties.
        Used when a class defines a custom __init__ AND class-level type annotations.
        The __init__ parameters are injected as constructor arguments; the class
        annotations are injected via setattr after instantiation.
        """
        sig = Signature.from_callable(self.concrete_type.__init__)
        params = {
            key: Dependency(key, value.annotation)
            for key, value in sig.parameters.items()
        }

        if sys.version_info >= (3, 10):  # pragma: no cover
            globalns = dict(vars(sys.modules[self.concrete_type.__module__]))
            globalns.update(_get_obj_globals(self.concrete_type))
            annotations = get_type_hints(
                self.concrete_type.__init__,
                globalns,
                _get_obj_locals(self.concrete_type),
            )
            for key, value in params.items():
                if key in annotations:
                    value.annotation = annotations[key]

        concrete_type = self.concrete_type
        init_fns = self._get_resolvers_for_parameters(concrete_type, context, params)

        ann_params = {
            key: Dependency(key, value) for key, value in extra_annotations.items()
        }
        ann_fns = self._get_resolvers_for_parameters(concrete_type, context, ann_params)
        annotation_resolvers = {
            name: ann_fns[i] for i, name in enumerate(ann_params.keys())
        }

        return get_mixed_type_provider(
            concrete_type, init_fns, annotation_resolvers, self.life_style, context
        )

    def __call__(self, context: ResolutionContext):
        concrete_type = self.concrete_type

        chain = context.dynamic_chain
        chain.append(concrete_type)

        if self._has_default_init():
            globalns = dict(vars(sys.modules[concrete_type.__module__]))
            globalns.update(_get_obj_globals(concrete_type))
            annotations = get_type_hints(
                concrete_type,
                globalns,
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

        # Custom __init__: also check for class-level annotations to inject as
        # properties. The cheap __annotations__ check avoids the expensive
        # get_type_hints call for the common case of no class-level annotations.
        if concrete_type.__annotations__:
            class_annotations = get_type_hints(
                concrete_type,
                {
                    **dict(vars(sys.modules[concrete_type.__module__])),
                    **_get_obj_globals(concrete_type),
                },
                _get_obj_locals(concrete_type),
            )
            if class_annotations:
                sig = Signature.from_callable(concrete_type.__init__)
                init_param_names = set(sig.parameters.keys()) - {"self"}
                extra_annotations = {
                    k: v
                    for k, v in class_annotations.items()
                    if k not in init_param_names
                    and not self._ignore_class_attribute(k, v)
                }
                if extra_annotations:
                    try:
                        return self._resolve_by_init_and_annotations(
                            context, extra_annotations
                        )
                    except RecursionError:
                        raise CircularDependencyException(chain[0], concrete_type)

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

    def __call__(self, context: ResolutionContext):
        if self.life_style == ServiceLifeStyle.SINGLETON:
            return SingletonFactoryTypeProvider(self.concrete_type, self.factory)

        if self.life_style == ServiceLifeStyle.SCOPED:
            return ScopedFactoryTypeProvider(self.concrete_type, self.factory)

        return FactoryTypeProvider(self.concrete_type, self.factory)


def _get_resolver_lifestyle(resolver) -> "ServiceLifeStyle":
    """Returns the ServiceLifeStyle of a resolver, defaulting to SINGLETON."""
    if isinstance(resolver, (DynamicResolver, FactoryResolver)):
        return resolver.life_style
    return ServiceLifeStyle.SINGLETON


class DecoratorResolver:
    """
    Resolver that wraps an existing resolver with a decorator class. The decorator
    must have an __init__ parameter whose type annotation matches (or is a supertype
    of) the registered base type; that parameter receives the inner service instance.
    All other __init__ parameters are resolved normally from the container.
    """

    __slots__ = (
        "_base_type",
        "_decorator_type",
        "_inner_resolver",
        "services",
        "life_style",
    )

    def __init__(self, base_type, decorator_type, inner_resolver, services, life_style):
        self._base_type = base_type
        self._decorator_type = decorator_type
        self._inner_resolver = inner_resolver
        self.services = services
        self.life_style = life_style

    def _get_resolver(self, desired_type, context: ResolutionContext):
        if desired_type in context.resolved:
            return context.resolved[desired_type]
        reg = self.services._map.get(desired_type)
        assert (
            reg is not None
        ), f"A resolver for type {class_name(desired_type)} is not configured"
        resolver = reg(context)
        context.resolved[desired_type] = resolver
        return resolver

    def __call__(self, context: ResolutionContext):
        inner_provider = self._inner_resolver(context)

        sig = Signature.from_callable(self._decorator_type.__init__)
        params = {
            key: Dependency(key, value.annotation)
            for key, value in sig.parameters.items()
        }

        globalns = dict(vars(sys.modules[self._decorator_type.__module__]))
        globalns.update(_get_obj_globals(self._decorator_type))
        try:
            annotations = get_type_hints(
                self._decorator_type.__init__,
                globalns,
                _get_obj_locals(self._decorator_type),
            )
            for key, value in params.items():
                if key in annotations:
                    value.annotation = annotations[key]
        except Exception:
            pass

        fns = []
        decoratee_found = False

        for param_name, dep in params.items():
            if param_name in ("self", "args", "kwargs"):
                continue

            annotation = dep.annotation
            if (
                annotation is not _empty
                and isclass(annotation)
                and annotation is not object
                and issubclass(self._base_type, annotation)
            ):
                fns.append(inner_provider)
                decoratee_found = True
            else:
                if annotation is _empty or annotation not in self.services._map:
                    raise CannotResolveParameterException(
                        param_name, self._decorator_type
                    )
                fns.append(self._get_resolver(annotation, context))

        if not decoratee_found:
            raise DecoratorRegistrationException(self._base_type, self._decorator_type)

        # Also resolve class-level annotations (property injection), excluding any
        # names already covered by __init__ params or ClassVar / pre-initialised attrs.
        init_param_names = set(params.keys())
        annotation_resolvers: dict[str, Callable] = {}

        if self._decorator_type.__annotations__:
            class_hints = get_type_hints(
                self._decorator_type,
                {
                    **dict(vars(sys.modules[self._decorator_type.__module__])),
                    **_get_obj_globals(self._decorator_type),
                },
                _get_obj_locals(self._decorator_type),
            )
            for attr_name, attr_type in class_hints.items():
                if attr_name in init_param_names:
                    continue
                is_classvar = getattr(attr_type, "__origin__", None) is ClassVar
                is_initialized = (
                    getattr(self._decorator_type, attr_name, None) is not None
                )
                if is_classvar or is_initialized:
                    continue
                if attr_type not in self.services._map:
                    raise CannotResolveParameterException(
                        attr_name, self._decorator_type
                    )
                annotation_resolvers[attr_name] = self._get_resolver(attr_type, context)

        decorator_type = self._decorator_type

        if annotation_resolvers:

            def factory(context, parent_type):
                instance = decorator_type(*[fn(context, parent_type) for fn in fns])
                for name, resolver in annotation_resolvers.items():
                    setattr(instance, name, resolver(context, parent_type))
                return instance

        else:

            def factory(context, parent_type):
                return decorator_type(*[fn(context, parent_type) for fn in fns])

        return FactoryResolver(decorator_type, factory, self.life_style)(context)


first_cap_re = re.compile("(.)([A-Z][a-z]+)")
all_cap_re = re.compile("([a-z0-9])([A-Z])")


def to_standard_param_name(name):
    value = all_cap_re.sub(r"\1_\2", first_cap_re.sub(r"\1_\2", name)).lower()
    if value.startswith("i_"):
        return "i" + value[2:]
    return value


class Services:
    """
    Provides methods to activate instances of classes, by cached activator functions.
    """

    __slots__ = ("_map", "_executors", "_scope_cls")

    def __init__(
        self,
        services_map=None,
        scope_cls: Type[ActivationScope] | None = None,
    ):
        if services_map is None:
            services_map = {}
        self._map = services_map
        self._executors = {}
        self._scope_cls = scope_cls or ActivationScope

    def __contains__(self, item):
        return item in self._map

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        self.set(key, value)

    def create_scope(
        self, scoped: dict[Type | str, Any] | None = None
    ) -> ActivationScope:
        return self._scope_cls(self, scoped)

    def set(self, new_type: Type | str, value: Any):
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
        desired_type: Type[T] | str,
        scope: ActivationScope | None = None,
        *,
        default: Any = ...,
    ) -> T:
        """
        Gets a service of the desired type, returning an activated instance.

        :param desired_type: desired service type.
        :param context: optional context, used to handle scoped services.
        :return: an instance of the desired type
        """
        if scope is None:
            scope = self.create_scope()

        resolver = self._map.get(desired_type)
        scoped_service = scope.scoped_services.get(desired_type) if scope else None

        if not resolver and not scoped_service:
            if default is not ...:
                return cast(T, default)
            raise CannotResolveTypeException(desired_type)

        return cast(T, scoped_service or resolver(scope, desired_type))

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

        annotations = _get_factory_annotations_or_throw(method)
        for key, value in params.items():
            if key in annotations:
                value.annotation = annotations[key]

        fns = []

        for key, value in params.items():
            fns.append(self._get_getter(key, value))

        if iscoroutinefunction(method):

            async def async_executor(
                scoped: dict[Type | str, Any] | None = None,
            ):
                with self.create_scope(scoped) as context:
                    return await method(*[fn(context) for fn in fns])

            return async_executor

        def executor(scoped: dict[Type | str, Any] | None = None):
            with self.create_scope(scoped) as context:
                return method(*[fn(context) for fn in fns])

        return executor

    def exec(
        self,
        method: Callable,
        scoped: dict[Type, Any] | None = None,
    ) -> Any:
        try:
            executor = self._executors[method]
        except KeyError:
            executor = self.get_executor(method)
            self._executors[method] = executor
        return executor(scoped)


FactoryCallableNoArguments = Callable[[], Any]
FactoryCallableSingleArgument = Callable[[ActivationScope], Any]
FactoryCallableTwoArguments = Callable[[ActivationScope, Type], Any]
FactoryCallableType = (
    FactoryCallableNoArguments
    | FactoryCallableSingleArgument
    | FactoryCallableTwoArguments
)


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


_ContainerSelf = TypeVar("_ContainerSelf", bound="Container")


class Container(ContainerProtocol):
    """
    Configuration class for a collection of services.
    """

    __slots__ = ("_map", "_aliases", "_exact_aliases", "_scope_cls", "strict")

    def __init__(
        self,
        *,
        strict: bool = False,
        scope_cls: Type[ActivationScope] | None = None,
    ) -> None:
        self._map: dict[Type, Callable] = {}
        self._aliases: DefaultDict[str, set[Type]] = defaultdict(set)
        self._exact_aliases: dict[str, Type] = {}
        self._provider: Services | None = None
        self._scope_cls = scope_cls
        self.strict = strict

    @property
    def provider(self) -> Services:
        if self._provider is None:
            self._provider = self.build_provider()
        return self._provider

    def __iter__(self) -> Iterator[tuple[Type, Callable]]:
        yield from self._map.items()

    def __contains__(self, key: object) -> bool:
        return key in self._map

    def bind_types(
        self: _ContainerSelf,
        obj_type: Any,
        concrete_type: Any = None,
        life_style: ServiceLifeStyle = ServiceLifeStyle.TRANSIENT,
    ) -> _ContainerSelf:
        try:
            assert issubclass(concrete_type, obj_type), (
                f"Cannot register {class_name(obj_type)} for abstract class "
                f"{class_name(concrete_type)}"
            )
        except TypeError:
            # ignore, this happens with generic types
            pass
        self._bind(obj_type, DynamicResolver(concrete_type, self, life_style))
        return self

    def register(
        self: _ContainerSelf,
        obj_type: Any,
        sub_type: Any = None,
        instance: Any = None,
        *args,
        **kwargs,
    ) -> _ContainerSelf:
        """
        Registers a type in this container.
        """
        if instance is not None:
            self.add_instance(instance, declared_class=obj_type)
            return self

        if sub_type is None:
            self._add_exact_transient(obj_type)
        else:
            self.add_transient(obj_type, sub_type)
        return self

    @overload
    def resolve(
        self,
        obj_type: Type[T],
        scope: Any = None,
        *args,
        **kwargs,
    ) -> T: ...

    @overload
    def resolve(
        self,
        obj_type: str,
        scope: Any = None,
        *args,
        **kwargs,
    ) -> Any: ...

    def resolve(
        self,
        obj_type: Type[T] | str,
        scope: Any = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Resolves a service by type, obtaining an instance of that type.
        """
        return self.provider.get(obj_type, scope=scope)

    def add_alias(
        self: _ContainerSelf,
        name: str,
        desired_type: Type,
    ) -> _ContainerSelf:
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

    def add_aliases(self: _ContainerSelf, values: AliasesTypeHint) -> _ContainerSelf:
        """
        Adds aliases to the set of inferred aliases.

        :param values: mapping object (parameter name: class)
        :return: self
        """
        for key, value in values.items():
            self.add_alias(key, value)
        return self

    def set_alias(
        self: _ContainerSelf,
        name: str,
        desired_type: Type,
        override: bool = False,
    ) -> _ContainerSelf:
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

    def set_aliases(
        self: _ContainerSelf,
        values: AliasesTypeHint,
        override: bool = False,
    ) -> _ContainerSelf:
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

        if self._provider is not None:
            self._provider = None

        key_name = class_name(key)

        if self.strict or "." in key_name:
            return

        self._aliases[key_name].add(key)
        self._aliases[key_name.lower()].add(key)
        self._aliases[to_standard_param_name(key_name)].add(key)

    def add_instance(
        self: _ContainerSelf, instance: Any, declared_class: Type | None = None
    ) -> _ContainerSelf:
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
        self: _ContainerSelf, base_type: Type, concrete_type: Type | None = None
    ) -> _ContainerSelf:
        """
        Registers a type by base type, to be instantiated with singleton lifetime.
        If a single type is given, the method `add_exact_singleton` is used.

        :param base_type: registered type. If a concrete type is provided, it must
        inherit the base type.
        :param concrete_type: concrete class
        :return: the service collection itself
        """
        if concrete_type is None:
            return self._add_exact_singleton(base_type)

        return self.bind_types(base_type, concrete_type, ServiceLifeStyle.SINGLETON)

    def add_scoped(
        self: _ContainerSelf,
        base_type: Type,
        concrete_type: Type | None = None,
    ) -> _ContainerSelf:
        """
        Registers a type by base type, to be instantiated with scoped lifetime.
        If a single type is given, the method `add_exact_scoped` is used.

        :param base_type: registered type. If a concrete type is provided, it must
        inherit the base type.
        :param concrete_type: concrete class
        :return: the service collection itself
        """
        if concrete_type is None:
            return self._add_exact_scoped(base_type)

        return self.bind_types(base_type, concrete_type, ServiceLifeStyle.SCOPED)

    def add_transient(
        self: _ContainerSelf,
        base_type: Type,
        concrete_type: Type | None = None,
    ) -> _ContainerSelf:
        """
        Registers a type by base type, to be instantiated with transient lifetime.
        If a single type is given, the method `add_exact_transient` is used.

        :param base_type: registered type. If a concrete type is provided, it must
        inherit the base type.
        :param concrete_type: concrete class
        :return: the service collection itself
        """
        if concrete_type is None:
            return self._add_exact_transient(base_type)

        return self.bind_types(base_type, concrete_type, ServiceLifeStyle.TRANSIENT)

    def decorate(
        self: _ContainerSelf,
        base_type: Type,
        decorator_type: Type,
    ) -> _ContainerSelf:
        """
        Registers a decorator for an already-registered type. The decorator wraps the
        existing service: when base_type is resolved, the decorator instance is returned
        with the inner service injected as the decorated dependency.

        The decorator class must have an __init__ parameter whose type annotation is
        base_type (or a supertype of it); that parameter receives the inner service.
        All other __init__ parameters are resolved from the container as usual.

        Calling decorate() multiple times for the same type chains the decorators —
        each wrapping the previous one (last registered = outermost decorator).

        :param base_type: the type being decorated (must already be registered)
        :param decorator_type: the decorator class
        :return: the service collection itself
        """
        existing = self._map.get(base_type)
        if existing is None:
            raise DecoratorRegistrationException(base_type, None)
        life_style = _get_resolver_lifestyle(existing)
        self._map[base_type] = DecoratorResolver(
            base_type, decorator_type, existing, self, life_style
        )
        if self._provider is not None:
            self._provider = None
        return self

    def _add_exact_singleton(
        self: _ContainerSelf, concrete_type: Type
    ) -> _ContainerSelf:
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

    def _add_exact_scoped(self: _ContainerSelf, concrete_type: Type) -> _ContainerSelf:
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

    def _add_exact_transient(
        self: _ContainerSelf, concrete_type: Type
    ) -> _ContainerSelf:
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
        self: _ContainerSelf,
        factory: FactoryCallableType,
        return_type: Type | None = None,
    ) -> _ContainerSelf:
        self.register_factory(factory, return_type, ServiceLifeStyle.SINGLETON)
        return self

    def add_transient_by_factory(
        self: _ContainerSelf,
        factory: FactoryCallableType,
        return_type: Type | None = None,
    ) -> _ContainerSelf:
        self.register_factory(factory, return_type, ServiceLifeStyle.TRANSIENT)
        return self

    def add_scoped_by_factory(
        self: _ContainerSelf,
        factory: FactoryCallableType,
        return_type: Type | None = None,
    ) -> _ContainerSelf:
        self.register_factory(factory, return_type, ServiceLifeStyle.SCOPED)
        return self

    @staticmethod
    def _check_factory(factory, signature, handled_type) -> Callable:
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
        return_type: Type | None,
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
            return_type,  # type: ignore
            FactoryResolver(
                return_type, self._check_factory(factory, sign, return_type), life_style
            ),
        )

    def build_provider(self) -> Services:
        """
        Builds and returns a service provider that can be used to activate and obtain
        services.

        The configuration of services is validated at this point, if any service cannot
        be instantiated due to missing dependencies, an exception is thrown inside this
        operation.

        :return: Service provider that can be used to activate and obtain services.
        """
        with ResolutionContext() as context:
            _map: dict[str | Type, Type] = {}

            for _type, resolver in self._map.items():
                if isinstance(resolver, DynamicResolver):
                    context.dynamic_chain.clear()

                if _type in context.resolved:
                    # assert _type not in context.resolved, "_map keys must be unique"
                    # check if its in the map
                    if _type in _map:
                        # NB: do not call resolver if one was already prepared for the
                        # type
                        raise OverridingServiceException(_type, resolver)
                    else:
                        resolved = context.resolved[_type]
                else:
                    # add to context so that we don't repeat operations
                    resolved = resolver(context)
                    context.resolved[_type] = resolved

                _map[_type] = resolved

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

        return Services(_map, scope_cls=self._scope_cls)

    @staticmethod
    def _get_alias_target_type(name, _map, _type):
        try:
            return _map[_type]
        except KeyError:
            raise AliasConfigurationError(name, _type)
