from rodi.exceptions.di_exception import DIException


class FactoryMissingContextException(DIException):
    def __init__(self, function) -> None:
        super().__init__(
            f"The factory '{function.__name__}' lacks locals and globals data. "
            "Decorate the function with the `@inject()` decorator defined in "
            "`rodi`. This is necessary since PEP 563."
        )
