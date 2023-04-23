class Dependency:
    __slots__ = ("name", "annotation")

    def __init__(self, name, annotation):
        self.name = name
        self.annotation = annotation
