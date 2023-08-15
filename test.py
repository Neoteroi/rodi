from rodi import Container


class MyContainer(Container):
    def register(
        self, obj_type, sub_type=None, instance=None, *args, **kwargs
    ) -> "Container":
        if obj_type in self._map:
            del self._map[obj_type]
        return super().register(obj_type, sub_type, instance, *args, **kwargs)


class BaseA:
    ...


class A1(BaseA):
    ...


class A2(BaseA):
    ...


container = MyContainer()


container.register(BaseA, A1)

container.register(BaseA, A2)

resolved = container.resolve(BaseA)
assert isinstance(resolved, A2)
