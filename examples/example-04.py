"""
This example illustrates the decorator pattern using Container.decorate().

The decorator pattern lets you wrap a registered service with another implementation
of the same interface, transparently adding behaviour (logging, caching, retries, etc.)
without modifying the original class.

Rules:
- The decorator class must implement (or be compatible with) the same interface.
- Its __init__ must have exactly one parameter whose type annotation matches the
  registered base type; that parameter receives the inner service instance.
- All other __init__ parameters (and class-level annotations) are resolved from the
  container as usual.
- Calling decorate() multiple times chains decorators — each call wraps the previous
  registration, so the last registered decorator is the outermost one.
"""
from abc import ABC, abstractmethod

from rodi import Container


# --- Domain interface ---


class MessageSender(ABC):
    @abstractmethod
    def send(self, message: str) -> None:
        """Sends a message."""


# --- Concrete implementation ---


class ConsoleSender(MessageSender):
    """Sends messages by printing them to the console."""

    def send(self, message: str) -> None:
        print(f"[console] {message}")


# --- Decorator 1: logging ---


class LoggingMessageSender(MessageSender):
    """Decorator that records every sent message before delegating."""

    def __init__(self, inner: MessageSender) -> None:
        self.inner = inner
        self.log: list[str] = []

    def send(self, message: str) -> None:
        self.log.append(message)
        self.inner.send(message)


# --- Decorator 2: prefixing (chained on top of the logging decorator) ---


class PrefixedMessageSender(MessageSender):
    """Decorator that prepends a fixed prefix to every message."""

    def __init__(self, inner: MessageSender) -> None:
        self.inner = inner

    def send(self, message: str) -> None:
        self.inner.send(f"[app] {message}")


# --- Wiring ---

container = Container()

container.add_singleton(MessageSender, ConsoleSender)
container.decorate(MessageSender, LoggingMessageSender)   # wraps ConsoleSender
container.decorate(MessageSender, PrefixedMessageSender)  # wraps LoggingMessageSender

sender = container.resolve(MessageSender)

# Resolution order: PrefixedMessageSender → LoggingMessageSender → ConsoleSender
assert isinstance(sender, PrefixedMessageSender)
assert isinstance(sender.inner, LoggingMessageSender)
assert isinstance(sender.inner.inner, ConsoleSender)

sender.send("Hello, world")
# prints: [console] [app] Hello, world

assert sender.inner.log == ["[app] Hello, world"]

# Singleton: same instance every time
assert sender is container.resolve(MessageSender)
