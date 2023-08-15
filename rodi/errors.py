from rodi.common import class_name


class DIException(Exception):
    """Base exception class for DI exceptions."""


class FactoryMissingContextException(DIException):
    def __init__(self, function) -> None:
        super().__init__(
            f"The factory '{function.__name__}' lacks locals and globals data. "
            "Decorate the function with the `@inject()` decorator defined in "
            "`rodi`. This is necessary since PEP 563."
        )


class CannotResolveTypeException(DIException):
    """
    Exception risen when it is not possible to resolve a Type."""

    def __init__(self, desired_type):
        super().__init__(f"Unable to resolve the type '{desired_type}'.")


class CannotResolveParameterException(DIException):
    """
    Exception risen when it is not possible to resolve a parameter,
    necessary to instantiate a type."""

    def __init__(self, param_name, desired_type):
        super().__init__(
            f"Unable to resolve parameter '{param_name}' "
            f"when resolving '{class_name(desired_type)}'"
        )


class UnsupportedUnionTypeException(DIException):
    """Exception risen when a parameter type is defined
    as Optional or Union of several types."""

    def __init__(self, param_name, desired_type):
        super().__init__(
            f"Union or Optional type declaration is not supported. "
            f"Cannot resolve parameter '{param_name}' "
            f"when resolving '{class_name(desired_type)}'"
        )


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


class CircularDependencyException(DIException):
    """Exception risen when a circular dependency between a type and
    one of its parameters is detected."""

    def __init__(self, expected_type, desired_type):
        super().__init__(
            "A circular dependency was detected for the service "
            f"of type '{class_name(expected_type)}' "
            f"for '{class_name(desired_type)}'"
        )


class InvalidOperationInStrictMode(DIException):
    def __init__(self):
        super().__init__(
            "The services are configured in strict mode, the operation is invalid."
        )


class AliasAlreadyDefined(DIException):
    """Exception risen when trying to add an alias that already exists."""

    def __init__(self, name):
        super().__init__(
            f"Cannot define alias '{name}'. "
            f"An alias with given name is already defined."
        )


class AliasConfigurationError(DIException):
    def __init__(self, name, _type):
        super().__init__(
            f"An alias '{name}' for type '{class_name(_type)}' was defined, "
            f"but the type was not configured in the Container."
        )


class MissingTypeException(DIException):
    """Exception risen when a type must be specified to use a factory"""

    def __init__(self):
        super().__init__(
            "Please specify the factory return type or "
            "annotate its return type; func() -> Foo:"
        )


class InvalidFactory(DIException):
    """Exception risen when a factory is not valid"""

    def __init__(self, _type):
        super().__init__(
            f"The factory specified for type {class_name(_type)} is not "
            "valid, it must be a function with either these signatures: "
            "def example_factory(context, type): "
            "or,"
            "def example_factory(context): "
            "or,"
            "def example_factory(): "
        )
