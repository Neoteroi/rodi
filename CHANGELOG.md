# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - ??? :star:
- Introduces a "ContainerProtocol" to improve interoperability between
  libraries and alternative implementations of DI containers. The protocol is
  inspired by [https://github.com/bobthemighty/punq](punq), since its interface
  is the most user-friendly and intelligible of those that were reviewed.
- Simplifies the code API of the library to support using the `Container` class
  to `register` and `resolve` services. The class `Services` is still used and
  available, but it's no more necessary to use it directly.
- Replaces `setup.py` with `pyproject.toml`.
- Renames context classes: "GetServiceContext" to "ActivationScope",
  "ResolveContext" to "ResolutionContext".

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
