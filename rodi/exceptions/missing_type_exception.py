from rodi.exceptions.di_exception import DIException


class MissingTypeException(DIException):
    """Exception risen when a type must be specified to use a factory"""

    def __init__(self):
        super().__init__(
            "Please specify the factory return type or "
            "annotate its return type; func() -> Foo:"
        )
