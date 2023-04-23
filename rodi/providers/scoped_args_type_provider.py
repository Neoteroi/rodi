from rodi.activation_scope import ActivationScope


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
