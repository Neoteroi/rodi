<!-- generated file, to update use: python examples-summary.py -->

# Examples

## example-01.py

This example illustrates a basic usage of the Container class to register
two types, and automatic resolution achieved through types inspection.

Two services are registered as "transient" services, meaning that a new instance is
created whenever needed.


## example-02.py

This example illustrates a basic usage of the Container class to register
a concrete type by base type, and its activation by base type.

This pattern helps writing code that is decoupled (e.g. business layer logic separated
from exact implementations of data access logic).


## example-03.py

This example illustrates how to configure a singleton object.
