from typing import Dict, Optional, Type, TypeVar

T = TypeVar("T")


class ActivationScope:
    __slots__ = ("scoped_services", "provider")

    def __init__(
        self,
        provider: Optional["Services"] = None,  # type: ignore # noqa: F821
        scoped_services: Optional[Dict[Type[T], T]] = None,
    ):
        self.provider = provider
        self.scoped_services = scoped_services or {}

    def __enter__(self):
        if self.scoped_services is None:
            self.scoped_services = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

    def dispose(self):
        if self.provider:
            self.provider = None

        if self.scoped_services:
            self.scoped_services.clear()
            self.scoped_services = None
