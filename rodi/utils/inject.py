import inspect
from typing import Any, Callable


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
