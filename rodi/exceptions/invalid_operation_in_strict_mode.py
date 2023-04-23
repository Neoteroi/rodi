from rodi.exceptions.di_exception import DIException


class InvalidOperationInStrictMode(DIException):
    def __init__(self):
        super().__init__(
            "The services are configured in strict mode, the operation is invalid."
        )
