from typing import Type, Mapping, Callable

from rodi.service_life_style import ServiceLifeStyle
from rodi.resolution_context import ResolutionContext
from rodi.resolvers.factory_resolver import FactoryResolver


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
