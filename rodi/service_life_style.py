from enum import Enum


class ServiceLifeStyle(Enum):
    TRANSIENT = 1
    SCOPED = 2
    SINGLETON = 3
