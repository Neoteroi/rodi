import sys
from inspect import Signature, _empty, isabstract, isclass
from typing import (
    ClassVar,
    Dict,
    Mapping,
    Type,
    Union,
    get_type_hints,
)

from rodi.resolution_context import ResolutionContext
from rodi.dependency import Dependency
from rodi.service_life_style import ServiceLifeStyle
from rodi.exceptions import (
    UnsupportedUnionTypeException,
    CannotResolveParameterException,
    CircularDependencyException,
)
from rodi.providers import (
    TypeProvider,
    ScopedTypeProvider,
    SingletonTypeProvider,
    ScopedArgsTypeProvider,
    ArgsTypeProvider,
)
from rodi.resolvers.factory_resolver import FactoryResolver
from rodi.utils.class_name import class_name
from rodi.utils.get_obj_locals import _get_obj_locals
from rodi.utils.get_annotations_type_provider import get_annotations_type_provider
from rodi.utils.get_plain_class_factory import _get_plain_class_factory


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
