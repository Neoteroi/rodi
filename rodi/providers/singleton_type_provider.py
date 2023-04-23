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
