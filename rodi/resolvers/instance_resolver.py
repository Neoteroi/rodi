from rodi.resolution_context import ResolutionContext
from rodi.providers.instance_provider import InstanceProvider
from rodi.utils.class_name import class_name


class InstanceResolver:
    __slots__ = ("instance",)

    def __init__(self, instance):
        self.instance = instance

    def __repr__(self):
        return f"<Singleton {class_name(self.instance.__class__)}>"

    def __call__(self, context: ResolutionContext):
        return InstanceProvider(self.instance)
