from typing import Protocol

from ..domain.contracts import ScopeDescriptor, ScopeSelection


class ScopeCatalog(Protocol):
    def resolve(self, selection: ScopeSelection) -> ScopeDescriptor: ...
