from rodi.activation_scope import ActivationScope


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
