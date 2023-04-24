import sys
from inspect import Signature, _empty, iscoroutinefunction
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union, cast

from rodi.activation_scope import ActivationScope
from rodi.dependency import Dependency
from rodi.exceptions import CannotResolveTypeException, OverridingServiceException
from rodi.utils.class_name import class_name
from rodi.utils.get_factory_annotations_or_throw import (
    _get_factory_annotations_or_throw,
)

T = TypeVar("T")


class Services:
    """
    Provides methods to activate instances of classes, by cached activator functions.
    """

    __slots__ = ("_map", "_executors")

    def __init__(self, services_map=None):
        if services_map is None:
            services_map = {}
        self._map = services_map
        self._executors = {}

    def __contains__(self, item):
        return item in self._map

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        self.set(key, value)

    def set(self, new_type: Union[Type, str], value: Any):
        """
        Sets a new service of desired type, as singleton.
        This method exists to increase interoperability of Services class (with dict).

        :param new_type:
        :param value:
        :return:
        """
        type_name = class_name(new_type)
        if new_type in self._map or (
            not isinstance(new_type, str) and type_name in self._map
        ):
            raise OverridingServiceException(self._map[new_type], new_type)

        def resolver(context, desired_type):
            return value

        self._map[new_type] = resolver
        if not isinstance(new_type, str):
            self._map[type_name] = resolver

    def get(
        self,
        desired_type: Union[Type[T], str],
        scope: Optional[ActivationScope] = None,
        *,
        default: Optional[Any] = ...,
    ) -> T:
        """
        Gets a service of the desired type, returning an activated instance.

        :param desired_type: desired service type.
        :param context: optional context, used to handle scoped services.
        :return: an instance of the desired type
        """
        if scope is None:
            scope = ActivationScope(self)

        resolver = self._map.get(desired_type)

        if not resolver:
            if default is not ...:
                return cast(T, default)
            raise CannotResolveTypeException(desired_type)

        return cast(T, resolver(scope, desired_type))

    def _get_getter(self, key, param):
        if param.annotation is _empty:

            def getter(context):
                return self.get(key, context)

        else:

            def getter(context):
                return self.get(param.annotation, context)

        getter.__name__ = f"<getter {key}>"
        return getter

    def get_executor(self, method: Callable) -> Callable:
        sig = Signature.from_callable(method)
        params = {
            key: Dependency(key, value.annotation)
            for key, value in sig.parameters.items()
        }

        if sys.version_info >= (3, 10):  # pragma: no cover
            # Python 3.10
            annotations = _get_factory_annotations_or_throw(method)
            for key, value in params.items():
                if key in annotations:
                    value.annotation = annotations[key]

        fns = []

        for key, value in params.items():
            fns.append(self._get_getter(key, value))

        if iscoroutinefunction(method):

            async def async_executor(scoped: Optional[Dict[Type, Any]] = None):
                with ActivationScope(self, scoped) as context:
                    return await method(*[fn(context) for fn in fns])

            return async_executor

        def executor(scoped: Optional[Dict[Type, Any]] = None):
            with ActivationScope(self, scoped) as context:
                return method(*[fn(context) for fn in fns])

        return executor

    def exec(
        self,
        method: Callable,
        scoped: Optional[Dict[Type, Any]] = None,
    ) -> Any:
        try:
            executor = self._executors[method]
        except KeyError:
            executor = self.get_executor(method)
            self._executors[method] = executor
        return executor(scoped)
