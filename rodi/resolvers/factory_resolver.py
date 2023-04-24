from rodi.providers import FactoryTypeProvider, ScopedFactoryTypeProvider
from rodi.providers.singleton_factory_type_provider import SingletonFactoryTypeProvider
from rodi.resolution_context import ResolutionContext
from rodi.service_life_style import ServiceLifeStyle


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
