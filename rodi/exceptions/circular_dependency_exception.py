from rodi.exceptions.di_exception import DIException
from rodi.utils.class_name import class_name


class CircularDependencyException(DIException):
    """Exception risen when a circular dependency between a type and
    one of its parameters is detected."""

    def __init__(self, expected_type, desired_type):
        super().__init__(
            "A circular dependency was detected for the service "
            f"of type '{class_name(expected_type)}' "
            f"for '{class_name(desired_type)}'"
        )
