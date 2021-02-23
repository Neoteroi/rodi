![Build](https://github.com/Neoteroi/rodi/workflows/Build/badge.svg)
[![pypi](https://img.shields.io/pypi/v/rodi.svg)](https://pypi.python.org/pypi/rodi)
[![versions](https://img.shields.io/pypi/pyversions/rodi.svg)](https://github.com/Neoteroi/rodi)
[![codecov](https://codecov.io/gh/Neoteroi/rodi/branch/master/graph/badge.svg?token=VzAnusWIZt)](https://codecov.io/gh/Neoteroi/rodi)
[![license](https://img.shields.io/github/license/Neoteroi/rodi.svg)](https://github.com/Neoteroi/rodi/blob/master/LICENSE)

# Implementation of dependency injection for Python 3

**Features:**
* types resolution by signature types annotations (_type hints_)
* types resolution by class annotations (_type hints_) (new in version 1.1.0 :star:)
* types resolution by constructor parameter names and aliases (_convention over
  configuration_)
* unintrusive: builds objects graph **without** the need to change classes
  source code (unlike some other Python implementations of dependency
  injection, like _[inject](https://pypi.org/project/Inject/)_)
* minimum overhead to obtain services, once the objects graph is built
* support for singletons, transient, and scoped services
* compatible with [Python
  3.10.0a5](https://github.com/Neoteroi/rodi/wiki/Compatibility-with-Python-3.10.0a5)
  (still in development at the time of rodi 1.1.1)

This library is freely inspired by .NET Standard
`Microsoft.Extensions.DependencyInjection` implementation (_ref. [MSDN,
Dependency injection in ASP.NET
Core](https://docs.microsoft.com/en-us/aspnet/core/fundamentals/dependency-injection?view=aspnetcore-2.1),
[Using dependency injection in a .Net Core console
application](https://andrewlock.net/using-dependency-injection-in-a-net-core-console-application/)_).

## Installation

```bash
pip install rodi
```

## De gustibus non disputandum est
This library is designed to work both by type hints in constructor signatures,
and by constructor parameter names (convention over configuration), like
described in below diagram. It can be useful for those who like type hinting,
those who don't, and those who like having both options.

![Usage
option](https://raw.githubusercontent.com/Neoteroi/rodi/master/documentation/rodi-design-taste.png
"Usage option")

## Minimum overhead
`rodi` works by inspecting __&#95;&#95;init&#95;&#95;__ methods **once** at
runtime, to generate functions that return instances of desired types.
Validation steps, for example to detect circular dependencies or missing
services, are done when building these functions, so additional validation is
not needed when activating services.

For this reason, services are first registered inside an instance of
_Container_ class, which implements a method _build&#95;provider()_ that
returns an instance of _Services_. The service provider is then used to obtain
desired services by type or name. Inspection and validation steps are done only
when creating an instance of service provider.

![Classes](https://raw.githubusercontent.com/Neoteroi/rodi/master/documentation/classes.png
"Classes")

In the example below, a singleton is registered by exact instance.

```python
container = Container()
container.add_instance(Cat("Celine"))

services = container.build_provider()  # --> validation, generation of functions

cat = services.get(Cat)

assert cat is not None
assert cat.name == "Celine"
```

## Service life style:
* singleton - instantiated only once per service provider
* transient - services are instantiated every time they are required
* scoped - instantiated only once per service resolution (root call, e.g. once
  per web request)

## Usage in BlackSheep
`rodi` is used in the [BlackSheep](https://www.neoteroi.dev/blacksheep/) web
framework to implement [dependency
injection](https://www.neoteroi.dev/blacksheep/dependency-injection/) for
request handlers.

# Documentation
For documentation and examples, please refer to the [wiki in GitHub,
https://github.com/Neoteroi/rodi/wiki](https://github.com/Neoteroi/rodi/wiki).
