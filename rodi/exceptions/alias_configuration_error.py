from rodi.exceptions.di_exception import DIException
from rodi.utils.class_name import class_name


class AliasConfigurationError(DIException):
    def __init__(self, name, _type):
        super().__init__(
            f"An alias '{name}' for type '{class_name(_type)}' was defined, "
            f"but the type was not configured in the Container."
        )
