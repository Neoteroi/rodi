![Build](https://github.com/Neoteroi/rodi/workflows/Build/badge.svg)
[![pypi](https://img.shields.io/pypi/v/rodi.svg)](https://pypi.python.org/pypi/rodi)
[![versions](https://img.shields.io/pypi/pyversions/rodi.svg)](https://github.com/Neoteroi/rodi)
[![codecov](https://codecov.io/gh/Neoteroi/rodi/branch/main/graph/badge.svg?token=VzAnusWIZt)](https://codecov.io/gh/Neoteroi/rodi)
[![license](https://img.shields.io/github/license/Neoteroi/rodi.svg)](https://github.com/Neoteroi/rodi/blob/main/LICENSE)
[![documentation](https://img.shields.io/badge/📖-docs-purple)](https://www.neoteroi.dev/rodi/)

# Implementation of dependency injection for Python 3

**Features:**

* types resolution by signature types annotations (_type hints_)
* types resolution by class annotations (_type hints_)
* types resolution by names and aliases (_convention over configuration_)
* unintrusive: builds objects graph **without** the need to change the
  source code of classes
* minimum overhead to obtain services, once the objects graph is built
* support for singletons, transient, and scoped services

This library is freely inspired by .NET Standard
`Microsoft.Extensions.DependencyInjection` implementation (_ref. [MSDN,
Dependency injection in ASP.NET
Core](https://docs.microsoft.com/en-us/aspnet/core/fundamentals/dependency-injection?view=aspnetcore-2.1),
[Using dependency injection in a .Net Core console
application](https://andrewlock.net/using-dependency-injection-in-a-net-core-console-application/)_).
The `ContainerProtocol` for v2 is inspired by [punq](https://github.com/bobthemighty/punq).

## Documentation

Rodi is documented here: [https://www.neoteroi.dev/rodi/](https://www.neoteroi.dev/rodi/).

## Installation

```bash
pip install rodi
```

## Efficient

`rodi` works by inspecting code **once** at runtime, to generate
functions that return instances of desired types - as long as the object graph
is not altered. Inspections are done either on constructors
(__&#95;&#95;init&#95;&#95;__) or class annotations. Validation steps, for
example to detect circular dependencies or missing services, are done when
building these functions, so additional validation is not needed when
activating services.

## Flexible

`rodi` offers two code APIs:

- one is kept as generic as possible, using a `ContainerProtocol` for scenarios
  in which it is desirable being able to replace `rodi` with alternative
  implementations of dependency injection for Python. The protocol only expects
  a class being able to `register` and `resolve` types, and to tell if a type
  is configured in it (`__contains__`). Even if other implementations of DI
  don´t implement these three methods, it should be easy to use
  [composition](https://en.wikipedia.org/wiki/Composition_over_inheritance) to
  wrap other libraries with a compatible class.
- one is a more concrete implementation, for scenarios where it's not desirable
  to consider alternative implementations of dependency injection.

For this reason, the examples report two ways to achieve certain things.

### Examples

For examples, refer to the [examples folder](./examples).

### Recommended practices

All services should be configured once, when an application starts, and the
object graph should *not* be altered during normal program execution.
Example: if you build a web application, configure the object graph when
bootstrapping the application, avoid altering the `Container` configuration
while handling web requests.

Aim at keeping the `Container` and service graphs abstracted from the front-end
layer of your application, and avoid mixing runtime values with container
configuration. Example: if you build a web application, avoid if possible
relying on the HTTP Request object being a service registered in your container.

## Service life style:

* singleton - instantiated only once per service provider
* transient - services are instantiated every time they are required
* scoped - instantiated only once per root service resolution call
  (e.g. once per web request)

## Usage in BlackSheep

`rodi` is used in the [BlackSheep](https://www.neoteroi.dev/blacksheep/)
web framework to implement [dependency injection](https://www.neoteroi.dev/blacksheep/dependency-injection/) for
request handlers.
