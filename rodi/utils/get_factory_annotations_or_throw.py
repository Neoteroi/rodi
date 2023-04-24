from typing import get_type_hints

from rodi.exceptions import FactoryMissingContextException


def _get_factory_annotations_or_throw(factory):
    factory_locals = getattr(factory, "_locals", None)
    factory_globals = getattr(factory, "_globals", None)

    if factory_locals is None:
        raise FactoryMissingContextException(factory)

    return get_type_hints(factory, globalns=factory_globals, localns=factory_locals)
