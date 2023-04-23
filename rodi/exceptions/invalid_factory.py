from rodi.exceptions.di_exception import DIException
from rodi.utils.class_name import class_name


class InvalidFactory(DIException):
    """Exception risen when a factory is not valid"""

    def __init__(self, _type):
        super().__init__(
            f"The factory specified for type {class_name(_type)} is not "
            f"valid, it must be a function with either these signatures: "
            f"def example_factory(context, type): "
            f"or,"
            f"def example_factory(context): "
            f"or,"
            f"def example_factory(): "
        )
