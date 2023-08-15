import sys
from inspect import Signature, _empty, isabstract, isclass
from typing import Any, Callable, ClassVar, Dict, Mapping, Type, Union, get_type_hints

from rodi.common import class_name, get_obj_locals
from rodi.errors import (
    CannotResolveParameterException,
    CircularDependencyException,
    UnsupportedUnionTypeException,
)
from rodi.services import ActivationScope, Dependency, ServiceLifeStyle


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
        return reg(context)

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

    def _resolve_by_init_method(self, context: ResolutionContext):
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
                get_obj_locals(self.concrete_type),
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
        """
        try:
            return value.__origin__ is ClassVar
        except AttributeError:
            return False

    def _resolve_by_annotations(
        self, context: ResolutionContext, annotations: Dict[str, Type]
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

    def __call__(self, context: ResolutionContext):
        concrete_type = self.concrete_type

        chain = context.dynamic_chain
        chain.append(concrete_type)

        if getattr(concrete_type, "__init__") is object.__init__:
            annotations = get_type_hints(
                concrete_type,
                vars(sys.modules[concrete_type.__module__]),
                get_obj_locals(concrete_type),
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

    def __call__(self, context: ResolutionContext):
        if self.life_style == ServiceLifeStyle.SINGLETON:
            return SingletonFactoryTypeProvider(self.concrete_type, self.factory)

        if self.life_style == ServiceLifeStyle.SCOPED:
            return ScopedFactoryTypeProvider(self.concrete_type, self.factory)

        return FactoryTypeProvider(self.concrete_type, self.factory)


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
    resolver_context: ResolutionContext,
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

    def __call__(self, context: ResolutionContext):
        return InstanceProvider(self.instance)


FactoryCallableNoArguments = Callable[[], Any]
FactoryCallableSingleArgument = Callable[[ActivationScope], Any]
FactoryCallableTwoArguments = Callable[[ActivationScope, Type], Any]
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
