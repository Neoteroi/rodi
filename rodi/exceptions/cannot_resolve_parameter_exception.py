from rodi.exceptions.di_exception import DIException
from rodi.utils.class_name import class_name


class CannotResolveParameterException(DIException):
    """
    Exception risen when it is not possible to resolve a parameter,
    necessary to instantiate a type."""

    def __init__(self, param_name, desired_type):
        super().__init__(
            f"Unable to resolve parameter '{param_name}' "
            f"when resolving '{class_name(desired_type)}'"
        )
