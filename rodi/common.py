import inspect
import re
from typing import Any, Callable, Dict, Optional, Type, get_type_hints

AliasesTypeHint = Dict[str, Type]


first_cap_re = re.compile("(.)([A-Z][a-z]+)")
all_cap_re = re.compile("([a-z0-9])([A-Z])")


def to_standard_param_name(name):
    value = all_cap_re.sub(r"\1_\2", first_cap_re.sub(r"\1_\2", name)).lower()
    if value.startswith("i_"):
        return "i" + value[2:]
    return value


def inject(globalsns=None, localns=None) -> Callable[..., Any]:
    """
    Marks a class or a function as injected. This method is only necessary if the class
    uses locals and the user uses Python >= 3.10, to bind the function's locals to the
    factory.
    """
    if localns is None or globalsns is None:
        frame = inspect.currentframe()
        try:
            if localns is None:
                localns = frame.f_back.f_locals  # type: ignore
            if globalsns is None:
                globalsns = frame.f_back.f_globals  # type: ignore
        finally:
            del frame

    def decorator(f):
        f._locals = localns
        f._globals = globalsns
        return f

    return decorator


def get_factory_annotations_or_throw(factory):
    factory_locals = getattr(factory, "_locals", None)
    factory_globals = getattr(factory, "_globals", None)

    if factory_locals is None:
        from rodi.errors import FactoryMissingContextException

        raise FactoryMissingContextException(factory)

    return get_type_hints(factory, globalns=factory_globals, localns=factory_locals)


def get_obj_locals(obj) -> Optional[Dict[str, Any]]:
    return getattr(obj, "_locals", None)


def class_name(input_type):
    if input_type in {list, set} and str(  # noqa: E721
        type(input_type) == "<class 'types.GenericAlias'>"
    ):
        # for Python 3.9 list[T], set[T]
        return str(input_type)
    try:
        return input_type.__name__
    except AttributeError:
        # for example, this is the case for List[str], Tuple[str, ...], etc.
        return str(input_type)
