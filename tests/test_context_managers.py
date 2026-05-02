import pytest
from pytest import raises

from rodi import (
    Container,
    InvalidContextManagerRegistration,
    ServiceLifeStyle,
)


class SyncCM:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False
        self.exit_exc: BaseException | None = None

    def __enter__(self) -> "SyncCM":
        self.entered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.exited = True
        self.exit_exc = exc_val


class SyncCMDep:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    def __enter__(self) -> "SyncCMDep":
        self.entered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.exited = True


class FailingEnter:
    def __init__(self, dep: SyncCMDep) -> None:
        self.dep = dep

    def __enter__(self):
        raise RuntimeError("boom")

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class NotACM:
    pass


class AsyncCM:
    def __init__(self) -> None:
        self.aentered = False
        self.aexited = False

    async def __aenter__(self) -> "AsyncCM":
        self.aentered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.aexited = True


def test_default_is_unmanaged():
    container = Container()
    container.add_scoped(SyncCM)
    provider = container.build_provider()

    with provider.create_scope() as scope:
        instance = scope.get(SyncCM)
        assert instance.entered is False

    assert instance.exited is False


def test_scoped_managed_enter_and_exit():
    container = Container()
    container.add_scoped(SyncCM, manage_context=True)
    provider = container.build_provider()

    with provider.create_scope() as scope:
        a = scope.get(SyncCM)
        b = scope.get(SyncCM)
        assert a is b
        assert a.entered is True
        assert a.exited is False

    assert a.exited is True


def test_transient_managed_enter_per_instance():
    container = Container()
    container.add_transient(SyncCM, manage_context=True)
    provider = container.build_provider()

    instances: list[SyncCM] = []
    with provider.create_scope() as scope:
        for _ in range(3):
            instances.append(scope.get(SyncCM))

        assert len(set(id(i) for i in instances)) == 3
        assert all(i.entered for i in instances)
        assert not any(i.exited for i in instances)

    assert all(i.exited for i in instances)


_lifo_order: list[str] = []


class _Inner:
    def __enter__(self):
        _lifo_order.append("enter inner")
        return self

    def __exit__(self, *a):
        _lifo_order.append("exit inner")


class _Outer:
    def __init__(self, inner: _Inner) -> None:
        self.inner = inner

    def __enter__(self):
        _lifo_order.append("enter outer")
        return self

    def __exit__(self, *a):
        _lifo_order.append("exit outer")


def test_lifo_exit_order():
    _lifo_order.clear()

    container = Container()
    container.add_scoped(_Inner, manage_context=True)
    container.add_scoped(_Outer, manage_context=True)
    provider = container.build_provider()

    with provider.create_scope() as scope:
        scope.get(_Outer)

    assert _lifo_order == ["enter inner", "enter outer", "exit outer", "exit inner"]


def test_exit_receives_exception_when_block_raises():
    container = Container()
    container.add_scoped(SyncCM, manage_context=True)
    provider = container.build_provider()

    instance: SyncCM | None = None
    with raises(RuntimeError, match="oops"):
        with provider.create_scope() as scope:
            instance = scope.get(SyncCM)
            raise RuntimeError("oops")

    assert instance is not None
    assert instance.exited is True
    assert isinstance(instance.exit_exc, RuntimeError)


def test_failure_in_enter_unwinds_already_entered():
    container = Container()
    container.add_scoped(SyncCMDep, manage_context=True)
    container.add_scoped(FailingEnter, manage_context=True)
    provider = container.build_provider()

    dep: SyncCMDep | None = None
    with raises(RuntimeError, match="boom"):
        with provider.create_scope() as scope:
            dep = scope.get(SyncCMDep)
            scope.get(FailingEnter)

    assert dep is not None
    assert dep.entered is True
    assert dep.exited is True


def test_resolve_non_cm_with_manage_context_raises():
    container = Container()
    container.add_scoped(NotACM, manage_context=True)
    provider = container.build_provider()

    with provider.create_scope() as scope:
        with raises(TypeError, match="context manager protocol"):
            scope.get(NotACM)


def test_singleton_with_manage_context_rejected_in_add_singleton():
    container = Container()
    with raises(InvalidContextManagerRegistration):
        container.add_singleton(SyncCM, manage_context=True)


def test_singleton_with_manage_context_rejected_via_factory():
    def factory() -> SyncCM:
        return SyncCM()

    container = Container()
    with raises(InvalidContextManagerRegistration):
        container.register_factory(
            factory, SyncCM, ServiceLifeStyle.SINGLETON, manage_context=True
        )


def test_factory_registration_managed_scoped():
    container = Container()
    container.add_scoped_by_factory(
        lambda: SyncCMDep(), SyncCMDep, manage_context=True
    )
    provider = container.build_provider()

    with provider.create_scope() as scope:
        instance = scope.get(SyncCMDep)
        assert instance.entered is True

    assert instance.exited is True


def test_register_kwarg_manage_context():
    container = Container()
    container.register(SyncCM, manage_context=True)
    provider = container.build_provider()

    with provider.create_scope() as scope:
        a = scope.get(SyncCM)
        b = scope.get(SyncCM)
        assert a is not b
        assert a.entered and b.entered

    assert a.exited and b.exited


@pytest.mark.asyncio
async def test_async_scope_manages_async_cm():
    container = Container()
    container.add_scoped(AsyncCM, manage_context=True)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        instance = await scope.aget(AsyncCM)
        assert instance.aentered is True
        assert instance.aexited is False

    assert instance.aexited is True


@pytest.mark.asyncio
async def test_async_scope_managed_transient():
    container = Container()
    container.add_transient(AsyncCM, manage_context=True)
    provider = container.build_provider()

    instances: list[AsyncCM] = []
    async with provider.create_async_scope() as scope:
        for _ in range(3):
            instances.append(await scope.aget(AsyncCM))
        assert all(i.aentered for i in instances)
        assert not any(i.aexited for i in instances)

    assert all(i.aexited for i in instances)


_async_lifo_order: list[str] = []


class _AsyncInner:
    async def __aenter__(self):
        _async_lifo_order.append("enter inner")
        return self

    async def __aexit__(self, *a):
        _async_lifo_order.append("exit inner")


class _AsyncOuter:
    def __init__(self, inner: _AsyncInner) -> None:
        self.inner = inner

    async def __aenter__(self):
        _async_lifo_order.append("enter outer")
        return self

    async def __aexit__(self, *a):
        _async_lifo_order.append("exit outer")


@pytest.mark.asyncio
async def test_async_scope_lifo_exit_order():
    _async_lifo_order.clear()

    container = Container()
    container.add_scoped(_AsyncInner, manage_context=True)
    container.add_scoped(_AsyncOuter, manage_context=True)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        await scope.aget(_AsyncOuter)

    assert _async_lifo_order == [
        "enter inner",
        "enter outer",
        "exit outer",
        "exit inner",
    ]


_mixed_order: list[str] = []


class _MixedSync:
    def __enter__(self):
        _mixed_order.append("enter sync")
        return self

    def __exit__(self, *a):
        _mixed_order.append("exit sync")


class _MixedAsync:
    def __init__(self, dep: _MixedSync) -> None:
        self.dep = dep

    async def __aenter__(self):
        _mixed_order.append("enter async")
        return self

    async def __aexit__(self, *a):
        _mixed_order.append("exit async")


@pytest.mark.asyncio
async def test_async_scope_mixed_sync_and_async_cms():
    _mixed_order.clear()

    container = Container()
    container.add_scoped(_MixedSync, manage_context=True)
    container.add_scoped(_MixedAsync, manage_context=True)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        await scope.aget(_MixedAsync)

    assert _mixed_order == ["enter sync", "enter async", "exit async", "exit sync"]


@pytest.mark.asyncio
async def test_async_scope_exit_receives_exception():
    container = Container()
    container.add_scoped(AsyncCM, manage_context=True)
    provider = container.build_provider()

    instance: AsyncCM | None = None
    with raises(RuntimeError, match="aboom"):
        async with provider.create_async_scope() as scope:
            instance = await scope.aget(AsyncCM)
            raise RuntimeError("aboom")

    assert instance is not None
    assert instance.aexited is True


def test_sync_scope_rejects_async_only_cm():
    container = Container()
    container.add_scoped(AsyncCM, manage_context=True)
    provider = container.build_provider()

    with provider.create_scope() as scope:
        with raises(TypeError, match="synchronous context manager protocol"):
            scope.get(AsyncCM)


@pytest.mark.asyncio
async def test_existing_unmanaged_scope_unchanged_async():
    container = Container()
    container.add_scoped(AsyncCM)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        instance = await scope.aget(AsyncCM)
        assert instance.aentered is False

    assert instance.aexited is False


_cross_protocol_order: list[str] = []


class _CrossSyncCM:
    def __enter__(self):
        _cross_protocol_order.append("enter sync")
        return self

    def __exit__(self, *a):
        _cross_protocol_order.append("exit sync")


class _CrossAsyncCM:
    async def __aenter__(self):
        _cross_protocol_order.append("enter async")
        return self

    async def __aexit__(self, *a):
        _cross_protocol_order.append("exit async")


@pytest.mark.asyncio
async def test_async_scope_cross_protocol_lifo():
    _cross_protocol_order.clear()

    container = Container()
    container.add_scoped(_CrossAsyncCM, manage_context=True)
    container.add_scoped(_CrossSyncCM, manage_context=True)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        await scope.aget(_CrossAsyncCM)
        scope.get(_CrossSyncCM)

    assert _cross_protocol_order == [
        "enter async",
        "enter sync",
        "exit sync",
        "exit async",
    ]


@pytest.mark.asyncio
async def test_async_scope_cross_protocol_lifo_reverse():
    _cross_protocol_order.clear()

    container = Container()
    container.add_scoped(_CrossAsyncCM, manage_context=True)
    container.add_scoped(_CrossSyncCM, manage_context=True)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        scope.get(_CrossSyncCM)
        await scope.aget(_CrossAsyncCM)

    assert _cross_protocol_order == [
        "enter sync",
        "enter async",
        "exit async",
        "exit sync",
    ]


class _DecoratedInner:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *a):
        self.exited = True


class _SyncDecorator:
    def __init__(self, inner: _DecoratedInner) -> None:
        self.inner = inner


def test_decorate_inner_managed_scoped():
    container = Container()
    container.add_scoped(_DecoratedInner, manage_context=True)
    container.decorate(_DecoratedInner, _SyncDecorator)
    provider = container.build_provider()

    with provider.create_scope() as scope:
        result = scope.get(_DecoratedInner)
        assert isinstance(result, _SyncDecorator)
        assert isinstance(result.inner, _DecoratedInner)
        assert result.inner.entered is True

    assert result.inner.exited is True


@pytest.mark.asyncio
async def test_aresolve_async_cm_with_async_scope():
    container = Container()
    container.add_scoped(AsyncCM, manage_context=True)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        instance = await container.aresolve(AsyncCM, scope)
        assert instance.aentered is True
        assert instance.aexited is False

    assert instance.aexited is True


@pytest.mark.asyncio
async def test_aresolve_managed_sync_cm_with_async_scope():
    container = Container()
    container.add_scoped(SyncCM, manage_context=True)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        instance = await container.aresolve(SyncCM, scope)
        assert instance.entered is True
        assert instance.exited is False

    assert instance.exited is True


@pytest.mark.asyncio
async def test_aresolve_unmanaged_service():
    container = Container()
    container.add_scoped(NotACM)
    provider = container.build_provider()

    async with provider.create_async_scope() as scope:
        instance = await container.aresolve(NotACM, scope)
        assert isinstance(instance, NotACM)


@pytest.mark.asyncio
async def test_aresolve_with_sync_scope_raises():
    container = Container()
    container.add_scoped(AsyncCM, manage_context=True)
    provider = container.build_provider()

    with provider.create_scope() as sync_scope:
        with raises(TypeError, match="aresolve requires an AsyncActivationScope"):
            await container.aresolve(AsyncCM, sync_scope)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_aresolve_with_none_scope_raises():
    container = Container()
    container.add_scoped(AsyncCM, manage_context=True)
    container.build_provider()

    with raises(TypeError, match="aresolve requires an AsyncActivationScope"):
        await container.aresolve(AsyncCM, None)  # type: ignore[arg-type]
