from rodi.activation_scope import ActivationScope


class FactoryTypeProvider:
    __slots__ = ("_type", "factory")

    def __init__(self, _type, factory):
        self._type = _type
        self.factory = factory

    def __call__(self, context: ActivationScope, parent_type):
        assert isinstance(context, ActivationScope)
        return self.factory(context, parent_type)
