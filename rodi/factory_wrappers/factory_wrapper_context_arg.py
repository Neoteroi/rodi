class FactoryWrapperContextArg:
    __slots__ = ("factory",)

    def __init__(self, factory):
        self.factory = factory

    def __call__(self, context, activating_type):
        return self.factory(context)
