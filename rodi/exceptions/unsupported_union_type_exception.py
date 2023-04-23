from rodi.exceptions.di_exception import DIException
from rodi.utils.class_name import class_name


class UnsupportedUnionTypeException(DIException):
    """Exception risen when a parameter type is defined
    as Optional or Union of several types."""

    def __init__(self, param_name, desired_type):
        super().__init__(
            f"Union or Optional type declaration is not supported. "
            f"Cannot resolve parameter '{param_name}' "
            f"when resolving '{class_name(desired_type)}'"
        )
