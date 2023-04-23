class ArgsTypeProvider:
    __slots__ = ("_type", "_args_callbacks")

    def __init__(self, _type, args_callbacks):
        self._type = _type
        self._args_callbacks = args_callbacks

    def __call__(self, context, parent_type):
        return self._type(*[fn(context, self._type) for fn in self._args_callbacks])
