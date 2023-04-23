from rodi.activation_scope import ActivationScope


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
