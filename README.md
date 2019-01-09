# Implementation of dependency injection for Python 3

**Features:**
* types resolution by signature types annotations (_type hints_)
* types resolution by constructor parameter names and aliases (_convention over configuration_)
* unintrusive: builds objects graph **without** the need to change classes source code (unlike some other Python implementations of dependency injection, like _[inject](https://pypi.org/project/Inject/)_)
* minimum overhead to obtain services, once the objects graph is built
* support for singletons, transient and scoped services

This library is freely inspired by .NET Standard `Microsoft.Extensions.DependencyInjection` implementation (_ref. [MSDN, Dependency injection in ASP.NET Core](https://docs.microsoft.com/en-us/aspnet/core/fundamentals/dependency-injection?view=aspnetcore-2.1), [Using dependency injection in a .Net Core console application](https://andrewlock.net/using-dependency-injection-in-a-net-core-console-application/)_).

The idea of writing this library was strengthened by this article by [Bob Gregory](https://twitter.com/bob_the_mighty): _[Dependency Injection with Type Signatures in Python](https://io.made.com/dependency-injection-with-type-signatures-in-python/)_. Even before reading Gregory's article, I shared many of the ideas he described in his blog.

## Installation

```bash
pip install rodi
```

## De gustibus non disputandum est
This library is designed to work both by type hints in constructor signatures, and by constructor parameter names (convention over configuration), like described in below diagram. It can be useful for those who like type hinting, those who don't, and those who like having both options.

![Usage option](https://raw.githubusercontent.com/RobertoPrevato/rodi/master/documentation/rodi-design-taste.png "Usage option")

## Minimum overhead
`rodi` works by inspecting __&#95;&#95;init&#95;&#95;__ methods **once** at runtime, to generate functions that return instances of desired types. Validation steps, for example to detect circular dependencies or missing services, are done when building these functions, so additional validation is not needed when activating services.

For this reason, services are first registered inside an instance of _Container_ class, which implements a method _build&#95;provider()_ that returns an instance of _Services_. The service provider is then used to obtain desired services by type or name. Inspection and validation steps are done only when creating an instance of service provider.

![Classes](https://raw.githubusercontent.com/RobertoPrevato/rodi/master/documentation/classes.png "Classes")

In the example below, a singleton is registered by exact instance.

```python
services = Container()
services.add_instance(Cat("Celine"))

provider = services.build_provider()  # --> validation, generation of functions

cat = provider.get(Cat)

assert cat is not None
assert cat.name == "Celine"
```

## Service life style:
* singleton - instantiated only once per service provider
* transient - services are instantiated every time they are required
* scoped - instantiated only once per service resolution (root call, e.g. once per web request)

# Documentation
For documentation and examples, please refer to the [wiki in GitHub, https://github.com/RobertoPrevato/rodi/wiki](https://github.com/RobertoPrevato/rodi/wiki).

---

# Develop and run tests locally
```bash
pip install -r dev_requirements.txt

# run tests using automatic discovery:
pytest
```
