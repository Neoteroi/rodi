class ResolutionContext:
    __slots__ = ("resolved", "dynamic_chain")
    __deletable__ = ("resolved",)

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
