from typing import Type


def _get_plain_class_factory(concrete_type: Type):
    def factory(*args):
        return concrete_type()

    return factory
