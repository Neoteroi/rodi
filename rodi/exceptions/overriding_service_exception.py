from rodi.exceptions.di_exception import DIException
from rodi.utils.class_name import class_name


class OverridingServiceException(DIException):
    """
    Exception risen when registering a service
    would override an existing one."""

    def __init__(self, key, value):
        key_name = key if isinstance(key, str) else class_name(key)
        super().__init__(
            f"A service with key '{key_name}' is already "
            f"registered and would be overridden by value {value}."
        )
