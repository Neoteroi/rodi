# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.6] - 2023-12-09 :hammer:
- Fixes import for Protocols support regardless of Python version (partially
  broken for Python 3.9), by @fennel-akunesh

## [2.0.5] - 2023-11-25 :lab_coat:
- Adds support for resolving `Protocol` classes even when they don't define an
  `__init__` method, by @lucas-labs
- Fixes bug in service provider build logic causing singletons to be instantiated
  n times when they are registered after its dependant, by @lucas-labs
- Changes the "ignore attributes" logic so that if a class variable has already
  been initialized externally, rodi doesn't attempt to reinitialize it (and to
  also prevent overriding it if the initialized class variable is also a
  registered object), by @lucas-labs

## [2.0.4] - 2023-10-28 :dragon:
- Fixes bug in Singleton implementation: stop singleton provider from recreating
  objects implementing `__len__`, by [Klavionik](https://github.com/Klavionik).
- Add Python 3.12 and remove Python 3.7 from the build matrix.

## [2.0.3] - 2023-08-14 :sun_with_face:
- Checks `scoped_services` before resolving from map when in a scope, by [StummeJ](https://github.com/StummeJ).
- Allow getting from scope context without needing to provide scope, by [StummeJ](https://github.com/StummeJ).

## [2.0.2] - 2023-03-31 :flamingo:
- Ignores `ClassVar` properties when resolving dependencies by class notations.
- Marks `rodi` 2 as stable.

## [2.0.1] - 2023-03-14 :croissant:
- Removes the strict requirement for resolved classes to have `__init__`
  methods defined, to add support for `Protocol`s that do not define an
  `__init__` method (thus using `*args`, `**kwargs`),
  [akhundMurad](https://github.com/akhundMurad)'s contribution.
- Corrects a code smell, replacing an `i` counter with `enumerate`,
  [GLEF1X](https://github.com/GLEF1X)'s contribution.

## [2.0.0] - 2023-01-07 :star:
- Introduces a `ContainerProtocol` to improve interoperability between
  libraries and alternative implementations of DI containers. The protocol is
  inspired by [punq](https://github.com/bobthemighty/punq), since its code API
  is the most user-friendly and intelligible of those that were reviewed.
  The `ContainerProtocol` can be used through [composition](https://en.wikipedia.org/wiki/Composition_over_inheritance)
  to replace `rodi` with alternative implementations of dependency injection in
  those libraries that use `DI`.
- Simplifies the code API of the library to support using the `Container` class
  to `register` and `resolve` services. The class `Services` is still used and
  available, but it's no more necessary to use it directly.
- Replaces `setup.py` with `pyproject.toml`.
- Renames context classes: "GetServiceContext" to "ActivationScope",
  "ResolveContext" to "ResolutionContext".
- The "add_exact*" methods have been made private, to simplify the public API.
- Improves type annotations; [MaximZayats](https://github.com/MaximZayats)' contribution.
- Adds typehints to GetServiceContext init params; [guscardvs](https://github.com/guscardvs)' contribution.

## [1.1.3] - 2022-03-27 :droplet:
- Corrects a bug that would cause false positives when raising exceptions
  for circular dependencies. The code now let recursion errors happen if they
  need to happen, re-raising a circular dependency error.

## [1.1.2] - 2022-03-14 :rabbit:
- Adds `py.typed` file.
- Applies `isort` and enforces `isort` and `black` checks in CI pipeline.
- Corrects the type annotation for `FactoryCallableType`.

## [1.1.1] - 2021-02-23 :cactus:
- Adds support for Generics and GenericAlias `Mapping[X, Y]`, `Iterable[T]`,
  `List[T]`, `Set[T]`, `Tuple[T, ...]`, Python 3.9 `list[T]`, etc. ([fixes
  #9](https://github.com/Neoteroi/rodi/issues/9)).
- Improves typing-friendliness making the `ServiceProvider.get` method
  returning a value of the input type.
- Adds support for Python 3.10.0a5 ✨. However, when classes and functions
  require locals, they need to be decorated. See [PEP
  563](https://www.python.org/dev/peps/pep-0563/).

## [1.1.0] - 2021-01-31 :grapes:
- Adds support to resolve class attributes annotations.
- Changes how classes without an `__init__` method are handled.
- Updates links to the GitHub organization, [Neoteroi](https://github.com/Neoteroi).

## [1.0.9] - 2020-11-08 :octocat:
- Completely migrates to GitHub Workflows.
- Improves build to test Python 3.6 and 3.9.
- Adds a changelog.
- Improves badges.
