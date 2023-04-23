from rodi.exceptions.di_exception import DIException


class CannotResolveTypeException(DIException):
    """
    Exception risen when it is not possible to resolve a Type."""

    def __init__(self, desired_type):
        super().__init__(f"Unable to resolve the type '{desired_type}'.")
