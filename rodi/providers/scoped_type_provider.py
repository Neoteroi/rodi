from rodi.activation_scope import ActivationScope


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
