"""
Functions exec tests.
exec functions are designed to enable executing any function injecting parameters.
"""

import pytest

from rodi import Container, inject


class Example:
    def __init__(self, repository):
        self.repository = repository


class Context:
    def __init__(self):
        self.trace_id = "1111"


class Repository:
    def __init__(self, context: Context):
        self.context = context


def test_execute_function():
    class Example:
        def __init__(self, repository):
            self.repository = repository

    class Context:
        def __init__(self):
            self.trace_id = "1111"

    @inject()
    class Repository:
        def __init__(self, context: Context):
            self.context = context

    called = False

    @inject()
    def fn(example, context: Context):
        nonlocal called
        called = True
        assert isinstance(example, Example)
        assert isinstance(example.repository, Repository)
        assert isinstance(context, Context)
        # scoped parameter:
        assert context is example.repository.context
        return context.trace_id

    container = Container()

    container.add_transient(Example)
    container.add_transient(Repository)
    container.add_scoped(Context)

    provider = container.build_provider()

    result = provider.exec(fn)

    assert called
    assert result == Context().trace_id


def test_executor():
    called = False

    @inject()
    def fn(example, context: Context):
        nonlocal called
        called = True
        assert isinstance(example, Example)
        assert isinstance(example.repository, Repository)
        assert isinstance(context, Context)
        # scoped parameter:
        assert context is example.repository.context
        return context.trace_id

    container = Container()

    container.add_transient(Example)
    container.add_transient(Repository)
    container.add_scoped(Context)

    provider = container.build_provider()

    executor = provider.get_executor(fn)

    result = executor()

    assert called
    assert result == Context().trace_id


def test_executor_with_given_scoped_services():
    called = False

    @inject()
    def fn(example, context: Context):
        nonlocal called
        called = True
        assert isinstance(example, Example)
        assert isinstance(example.repository, Repository)
        assert isinstance(context, Context)
        # scoped parameter:
        assert context is example.repository.context
        return context

    container = Container()

    container.add_transient(Example)
    container.add_transient(Repository)
    container.add_scoped(Context)

    provider = container.build_provider()

    executor = provider.get_executor(fn)

    given_context = Context()
    result = executor({Context: given_context})

    assert called
    assert result is given_context


@pytest.mark.asyncio
async def test_async_executor():
    called = False

    @inject()
    async def fn(example, context: Context):
        nonlocal called
        called = True
        assert isinstance(example, Example)
        assert isinstance(example.repository, Repository)
        assert isinstance(context, Context)
        # scoped parameter:
        assert context is example.repository.context
        return context.trace_id

    container = Container()

    container.add_transient(Example)
    container.add_transient(Repository)
    container.add_scoped(Context)

    provider = container.build_provider()

    executor = provider.get_executor(fn)

    result = await executor()

    assert called
    assert result == Context().trace_id
