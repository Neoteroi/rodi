import re
from enum import Enum
from collections import defaultdict
from typing import Optional, Union
from inspect import Signature, isclass, isabstract, _empty


class DIException(Exception):
    """Base exception class for DI exceptions."""


class ClassNotDefiningInitMethod(DIException):
    """Exception risen when a registered class does not implement a specific __init__ method"""

    def __init__(self, desired_type):
        super().__init__(f"Cannot activate an instance of '{desired_type.__name__}' "
                         f"because it does not implement a specific __init__ method.")


class CannotResolveParameterException(DIException):
    """Exception risen when it is not possible to resolve a parameter, necessary to instantiate a type."""

    def __init__(self, param_name, desired_type):
        super().__init__(f"Unable to resolve parameter '{param_name}' when resolving '{desired_type.__name__}'")


class AmbiguousReferenceName(DIException):
    """Exception risen when it is not possible to resolve a type by name, due to ambiguity."""

    def __init__(self, param_name, desired_type, aliases):
        super().__init__(f"Ambiguous reference name for parameter '{param_name}' when resolving "
                         f"'{desired_type.__name__}'. "
                         f"Possible values for this parameter: {aliases}"
                         f"Either specify parameter type or choose a unique name.")


class UnsupportedUnionTypeException(DIException):
    """Exception risen when a parameter type is defined as Optional or Union of several types."""

    def __init__(self, param_name, desired_type):
        super().__init__(f"Union or Optional type declaration is not supported. "
                         f"Cannot resolve parameter '{param_name}' when resolving '{desired_type.__name__}'")


class CannotResolveTypeException(DIException):
    """Exception risen when it is not possible to resolve a type because it is not registered."""

    def __init__(self, param_name, expected_type, desired_type):
        super().__init__(f"Unable to resolve type with name '{param_name}' and type '{expected_type.__name__}' "
                         f"when resolving '{desired_type.__name__}'")


class OverridingServiceException(DIException):
    """Exception risen when registering a service would override an existing one."""

    def __init__(self, key, value):
        key_name = key if isinstance(key, str) else key.__name__
        super().__init__(f"A service with key '{key_name}' is already "
                         f"registered and would be overridden by value {value}.")


class CircularDependencyException(DIException):
    """Exception risen when a circular dependency between a type and one of its parameters is detected."""

    def __init__(self, expected_type, desired_type):
        super().__init__(f"A circular dependency was detected for the service "
                         f"of type '{expected_type.__name__}' for '{desired_type.__name__}'")


class InvalidOperationInStrictMode(DIException):

    def __init__(self):
        super().__init__(f"The services are configured in strict mode, the operation is invalid.")


class AliasAlreadyDefined(DIException):
    """Exception risen when trying to add an alias that already exists."""

    def __init__(self, name):
        super().__init__(f"Cannot define alias '{name}'. "
                         f"Aliases are not used when services use strict mode (strict=True)")


class MissingTypeException(DIException):
    """Exception risen when a type must be specified to use a factory"""

    def __init__(self):
        super().__init__('Please specify the factory return type or annotate its return type; func() -> Foo:')


class InvalidFactory(DIException):
    """Exception risen when a factory is not valid"""

    def __init__(self, _type):
        super().__init__(f'The factory specified for type {_type.__name__} is not valid, '
                         f'it must be a function with either these signatures: '
                         f'def example_factory(context, type): '
                         f'or,'
                         f'def example_factory(context): '
                         f'or,'
                         f'def example_factory(): ')


class ServiceLifeStyle(Enum):
    TRANSIENT = 1
    SCOPED = 2
    SINGLETON = 3


class GetServiceContext:
    __slots__ = ('scoped_services', 'provider', 'types_chain')

    def __init__(self, provider=None):
        self.provider = provider
        self.scoped_services = {}
        self.types_chain = []

    def __enter__(self):
        if self.scoped_services is None:
            self.scoped_services = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

    @property
    def current_type(self):
        try:
            return self.types_chain[-1]
        except IndexError:
            return None

    def dispose(self):
        if self.provider:
            self.provider = None

        del self.types_chain[:]

        if self.scoped_services:
            self.scoped_services.clear()
            self.scoped_services = None


class ResolveContext:
    __slots__ = ('resolved', 'dynamic_chain')

    def __init__(self):
        self.resolved = {}
        self.dynamic_chain = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()

    def dispose(self):
        del self.resolved
        self.dynamic_chain.clear()


class InstanceProvider:
    __slots__ = ('instance',)

    def __init__(self, instance):
        self.instance = instance

    def __call__(self, context):
        return self.instance


class TypeProvider:
    __slots__ = ('_type',)

    def __init__(self, _type):
        self._type = _type

    def __call__(self, context):
        return self._type()


class ScopedTypeProvider:
    __slots__ = ('_type',)

    def __init__(self, _type):
        self._type = _type

    def __call__(self, context: GetServiceContext):
        if self._type in context.scoped_services:
            return context.scoped_services[self._type]

        service = self._type()
        context.scoped_services[self._type] = service
        return service


class ArgsTypeProvider:
    __slots__ = ('_type', '_args_callbacks')

    def __init__(self, _type, args_callbacks):
        self._type = _type
        self._args_callbacks = args_callbacks

    def __call__(self, context):
        context.types_chain.append(self._type)
        return self._type(*[fn(context) for fn in self._args_callbacks])


class FactoryTypeProvider:
    __slots__ = ('_type', 'factory')

    def __init__(self,
                 _type,
                 factory):
        self._type = _type
        self.factory = factory

    def __call__(self, context: GetServiceContext):
        return self.factory(context.provider, context.current_type)


class SingletonFactoryTypeProvider:
    __slots__ = ('_type', 'factory', 'instance')

    def __init__(self,
                 _type,
                 factory):
        self._type = _type
        self.factory = factory
        self.instance = None

    def __call__(self, context: GetServiceContext):
        if self.instance is None:
            self.instance = self.factory(context.provider, context.current_type)
        return self.instance


class ScopedFactoryTypeProvider:
    __slots__ = ('_type', 'factory')

    def __init__(self,
                 _type,
                 factory):
        self._type = _type
        self.factory = factory

    def __call__(self, context: GetServiceContext):
        if self._type in context.scoped_services:
            return context.scoped_services[self._type]

        instance = self.factory(context.provider, context.current_type)
        context.scoped_services[self._type] = instance
        return instance


class ScopedArgsTypeProvider:
    __slots__ = ('_type', '_args_callbacks')

    def __init__(self, _type, args_callbacks):
        self._type = _type
        self._args_callbacks = args_callbacks

    def __call__(self, context: GetServiceContext):
        context.types_chain.append(self._type)
        if self._type in context.scoped_services:
            return context.scoped_services[self._type]

        service = self._type(*[fn(context) for fn in self._args_callbacks])
        context.scoped_services[self._type] = service
        return service


class SingletonTypeProvider:
    __slots__ = ('_type', '_instance', '_args_callbacks')

    def __init__(self, _type, _args_callbacks):
        self._type = _type
        self._args_callbacks = _args_callbacks
        self._instance = None

    def __call__(self, context):
        context.types_chain.append(self._type)
        if not self._instance:
            self._instance = self._type(*[fn(context) for fn in self._args_callbacks]) \
                if self._args_callbacks else self._type()

        return self._instance


class InstanceResolver:
    __slots__ = ('instance',)

    def __init__(self, instance):
        self.instance = instance

    def __repr__(self):
        return f'<Singleton {self.instance.__class__.__name__}>'

    def __call__(self, context: ResolveContext):
        return InstanceProvider(self.instance)


class DynamicResolver:
    __slots__ = ('concrete_type',
                 'params',
                 'services',
                 'lifestyle')

    def __init__(self,
                 concrete_type,
                 services,
                 lifestyle):
        assert isclass(concrete_type)
        assert not isabstract(concrete_type)

        self.concrete_type = concrete_type
        self.services = services
        sig = Signature.from_callable(concrete_type.__init__)
        self.params = sig.parameters
        self.lifestyle = lifestyle

    def _get_resolver(self, desired_type, context: ResolveContext):
        # NB: the following two lines are important to ensure that singletons
        # are instantiated only once per service provider and to not repeat operations more than once
        if desired_type in context.resolved:
            return context.resolved[desired_type]

        reg = self.services._map.get(desired_type)
        if not reg:
            return None
        return reg(context)

    def __call__(self, context: ResolveContext):
        concrete_type = self.concrete_type

        chain = context.dynamic_chain
        if concrete_type in chain:
            raise CircularDependencyException(chain[0], concrete_type)

        chain.append(concrete_type)

        if getattr(concrete_type, '__init__') is object.__init__:
            raise ClassNotDefiningInitMethod(concrete_type)

        params = self.params

        if len(params) == 1:
            if self.lifestyle == ServiceLifeStyle.SINGLETON:
                return SingletonTypeProvider(concrete_type, None)

            if self.lifestyle == ServiceLifeStyle.SCOPED:
                return ScopedTypeProvider(concrete_type)

            return TypeProvider(concrete_type)

        fns = []
        services = self.services

        for param_name, param in params.items():
            if param_name == 'self':
                continue

            param_type = param.annotation

            if hasattr(param_type, '__origin__') and param_type.__origin__ is Union:
                # NB: we could cycle through possible types using: param_type.__args__
                # Right now Union and Optional types resolution is not implemented, but at least Optional
                # could be supported in the future
                raise UnsupportedUnionTypeException(param_name, concrete_type)

            if param_type is _empty:
                if not services.strict:
                    # support for exact, user defined aliases, without ambiguity
                    exact_alias = services._exact_aliases.get(param_name)

                    if exact_alias:
                        param_type = exact_alias
                    else:
                        aliases = services._aliases[param_name]

                        if aliases:
                            if len(aliases) > 1:
                                raise AmbiguousReferenceName(param_name, concrete_type, aliases)

                            for param_type in aliases:
                                break
                else:
                    raise CannotResolveParameterException(param_name, concrete_type)

            if param_type not in services._map:
                raise CannotResolveParameterException(param_name, concrete_type)

            if param_type in chain:
                raise CircularDependencyException(chain[0], param_type)

            param_resolver = self._get_resolver(param_type, context)

            if param_resolver is None:
                raise CannotResolveTypeException(param_name, param_type, concrete_type)

            fns.append(param_resolver)

        if self.lifestyle == ServiceLifeStyle.SINGLETON:
            return SingletonTypeProvider(concrete_type, fns)

        if self.lifestyle == ServiceLifeStyle.SCOPED:
            return ScopedArgsTypeProvider(concrete_type, fns)

        return ArgsTypeProvider(concrete_type, fns)


class FactoryResolver:
    __slots__ = ('concrete_type',
                 'factory',
                 'params',
                 'lifestyle')

    def __init__(self,
                 concrete_type,
                 factory,
                 lifestyle):
        assert isclass(concrete_type)
        assert not isabstract(concrete_type)

        self.factory = factory
        self.concrete_type = concrete_type
        self.lifestyle = lifestyle

    def __call__(self, context: ResolveContext):
        if self.lifestyle == ServiceLifeStyle.SINGLETON:
            return SingletonFactoryTypeProvider(self.concrete_type, self.factory)

        if self.lifestyle == ServiceLifeStyle.SCOPED:
            return ScopedFactoryTypeProvider(self.concrete_type, self.factory)

        return FactoryTypeProvider(self.concrete_type, self.factory)


first_cap_re = re.compile('(.)([A-Z][a-z]+)')
all_cap_re = re.compile('([a-z0-9])([A-Z])')


def to_standard_param_name(name):
    value = all_cap_re.sub(r'\1_\2', first_cap_re.sub(r'\1_\2', name)).lower()
    if value.startswith('i_'):
        return 'i' + value[2:]
    return value


class ServiceProvider:
    """Provides methods to activate instances of classes, by cached callback functions."""

    __slots__ = ('_map',)

    def __init__(self, map):
        self._map = map

    def __contains__(self, item):
        return item in self._map

    def get(self, desired_type: Union[type, str], context: Optional[GetServiceContext] = None):
        """Gets a service of desired type, returning an activated instance.

        :param desired_type: desired service type.
        :param context: optional context, used to handle scoped services.
        :return:
        """
        if context is None:
            context = GetServiceContext(self)

        reg = self._map.get(desired_type)

        if not reg:
            return None

        context.types_chain.append(desired_type)

        return reg(context=context)


class FactoryWrapperNoArgs:

    __slots__ = ('factory',)

    def __init__(self, factory):
        self.factory = factory

    def __call__(self, context, activating_type):
        return self.factory()


class FactoryWrapperContextArg:
    __slots__ = ('factory',)

    def __init__(self, factory):
        self.factory = factory

    def __call__(self, context, activating_type):
        return self.factory(context)


class ServiceCollection:
    """Represents a configuration class for collection of services."""

    __slots__ = ('_map', '_aliases', '_exact_aliases', 'strict')

    def __init__(self, strict=False):
        self._map = {}
        self._aliases = None if strict else defaultdict(set)
        self._exact_aliases = None if strict else {}
        self.strict = strict

    def __contains__(self, key):
        return key in self._map

    def register(self, base_type, concrete_type, lifestyle: ServiceLifeStyle):
        assert issubclass(concrete_type, base_type), \
            f'Cannot register {base_type.__name__} for abstract class {concrete_type.__name__}'

        self._bind(base_type, DynamicResolver(concrete_type, self, lifestyle))
        return self

    def add_alias(self, name, desired_type):
        """Adds an alias to the set of inferred aliases.

        :param name: parameter name
        :param desired_type: desired type by parameter name
        :return: self
        """
        if self.strict:
            raise InvalidOperationInStrictMode()
        if name in self._aliases:
            raise AliasAlreadyDefined(name)
        self._aliases[name].add(desired_type)
        return self

    def add_aliases(self, values):
        """Adds aliases to the set of inferred aliases.

        :param values: mapping object (parameter name: class)
        :return: self
        """
        for key, value in values.items():
            self.add_alias(key, value)
        return self

    def set_alias(self, name, desired_type, override=False):
        """Sets an exact alias for a desired type.

        :param name: parameter name
        :param desired_type: desired type by parameter name
        :param override: whether to override existing values, or throw exception
        :return: self
        """
        if self.strict:
            raise InvalidOperationInStrictMode()
        if not override and name in self._exact_aliases:
            raise AliasAlreadyDefined(name)
        self._exact_aliases[name] = desired_type
        return self

    def set_aliases(self, values, override=False):
        """Sets many exact aliases for desired types.

        :param values: mapping object (parameter name: class)
        :param override: whether to override existing values, or throw exception
        :return: self
        """
        for key, value in values.items():
            self.set_alias(key, value, override)
        return self

    def _bind(self, key, value):
        if key in self._map:
            raise OverridingServiceException(key, value)
        self._map[key] = value

        key_name = key.__name__
        self._aliases[key_name].add(key)
        self._aliases[key_name.lower()].add(key)
        self._aliases[to_standard_param_name(key_name)].add(key)

    def add_instance(self, instance, declared_class=None):
        """Registers an exact instance, optionally by declared class.

        :param instance: singleton to be registered
        :param declared_class: optionally, lets define the class used as reference of the singleton
        :return: the service collection itself
        """
        self._bind(instance.__class__ if not declared_class else declared_class, InstanceResolver(instance))
        return self

    def add_singleton(self, base_type, concrete_type):
        """Registers a type by base type, to be instantiated with singleton lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        return self.register(base_type, concrete_type, ServiceLifeStyle.SINGLETON)

    def add_scoped(self, base_type, concrete_type):
        """Registers a type by base type, to be instantiated with scoped lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        return self.register(base_type, concrete_type, ServiceLifeStyle.SCOPED)

    def add_transient(self, base_type, concrete_type):
        """Registers a type by base type, to be instantiated with transient lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        return self.register(base_type, concrete_type, ServiceLifeStyle.TRANSIENT)

    def add_exact_singleton(self, concrete_type):
        """Registers an exact type, to be instantiated with singleton lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        assert not isabstract(concrete_type)
        self._bind(concrete_type, DynamicResolver(concrete_type, self, ServiceLifeStyle.SINGLETON))
        return self

    def add_exact_scoped(self, concrete_type):
        """Registers an exact type, to be instantiated with scoped lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        assert not isabstract(concrete_type)
        self._bind(concrete_type, DynamicResolver(concrete_type, self, ServiceLifeStyle.SCOPED))
        return self

    def add_exact_transient(self, concrete_type):
        """Registers an exact type, to be instantiated with transient lifetime.

        :param concrete_type: concrete class
        :return: the service collection itself
        """
        assert not isabstract(concrete_type)
        self._bind(concrete_type, DynamicResolver(concrete_type, self, ServiceLifeStyle.TRANSIENT))
        return self

    def add_singleton_by_factory(self, factory, return_type=None):
        self.register_factory(factory, return_type, ServiceLifeStyle.SINGLETON)
        return self

    def add_transient_by_factory(self, factory, return_type=None):
        self.register_factory(factory, return_type, ServiceLifeStyle.TRANSIENT)
        return self

    def add_scoped_by_factory(self, factory, return_type=None):
        self.register_factory(factory, return_type, ServiceLifeStyle.SCOPED)
        return self

    def _check_factory(self, factory, signature, handled_type):
        if not callable(factory):
            raise InvalidFactory(handled_type)

        params_len = len(signature.parameters)

        if params_len == 0:
            return FactoryWrapperNoArgs(factory)

        if params_len == 1:
            return FactoryWrapperContextArg(factory)

        if params_len == 2:
            return factory

        raise InvalidFactory(handled_type)

    def register_factory(self, factory, return_type, life_style):
        assert callable(factory)

        sign = Signature.from_callable(factory)
        if not return_type:
            if sign.return_annotation is _empty:
                raise MissingTypeException()
            return_type = sign.return_annotation
        self._bind(return_type, FactoryResolver(return_type,
                                                self._check_factory(factory, sign, return_type),
                                                life_style))

    def build_provider(self) -> ServiceProvider:
        """Builds and returns a service provider that can be used to activate and obtain services.

        The configuration of services is validated at this point, if any service cannot be instantiated
        due to missing dependencies, an exception is thrown inside this operation.

        :return: Service provider that can be used to activate and obtain services.
        """
        with ResolveContext() as context:
            _map = {}

            for _type, resolver in self._map.items():
                # NB: do not call resolver if one was already prepared for the type
                if _type in context.resolved:
                    continue

                if isinstance(resolver, DynamicResolver):
                    context.dynamic_chain.clear()

                _map[_type] = resolver(context)
                context.resolved[_type] = _map[_type]
                _map[_type.__name__] = _map[_type]

            if not self.strict:
                # include aliases in the map;
                for name, _types in self._aliases.items():
                    if len(_types) > 1:
                        # ambiguous alias, ignore because an exception would have been already thrown by resolver()
                        continue
                    for _type in _types:
                        break
                    _map[name] = _map[_type]

                for name, _type in self._exact_aliases.items():
                    _map[name] = _map[_type]

        return ServiceProvider(_map)
