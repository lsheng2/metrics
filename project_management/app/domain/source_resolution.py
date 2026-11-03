from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceDependencyDefinition:
    filter_id: str
    query: str
    source_hash: str


@dataclass(frozen=True, slots=True)
class SourceResolutionInput:
    original_rule_hash: str
    provider_id: str
    endpoint_id: str
    principal_id: str
    effective_query: str
    dependencies: tuple[SourceDependencyDefinition, ...]
    resolver_revision: str


@dataclass(frozen=True, slots=True)
class SourceResolutionRef:
    resolution_hash: str
    commit_id: str
