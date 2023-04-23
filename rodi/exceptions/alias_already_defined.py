from rodi.exceptions.di_exception import DIException


class AliasAlreadyDefined(DIException):
    """Exception risen when trying to add an alias that already exists."""

    def __init__(self, name):
        super().__init__(
            f"Cannot define alias '{name}'. "
            f"An alias with given name is already defined."
        )
