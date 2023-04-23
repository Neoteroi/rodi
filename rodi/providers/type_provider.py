class TypeProvider:
    __slots__ = ("_type",)

    def __init__(self, _type):
        self._type = _type

    def __call__(self, context, parent_type):
        return self._type()
