class InstanceProvider:
    __slots__ = ("instance",)

    def __init__(self, instance):
        self.instance = instance

    def __call__(self, context, parent_type):
        return self.instance
