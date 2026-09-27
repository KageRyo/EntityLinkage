from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, TypeAlias

Scalar: TypeAlias = str | int | float | bool | None
LinkageStatus: TypeAlias = Literal["resolved", "ambiguous", "unresolved", "not_applicable"]
CandidateRuleType: TypeAlias = Literal["normalized_name", "exact_value"]
MissingBehavior: TypeAlias = Literal["ignore", "reject"]
OverrideStatus: TypeAlias = Literal["resolved", "not_applicable"]
EvidencePhase: TypeAlias = Literal["candidate", "constraint", "override"]
EvidenceValue: TypeAlias = Scalar | tuple[Scalar, ...]


def _readonly_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class Entity:
    id: str
    name: str
    aliases: tuple[str, ...] = ()
    attributes: Mapping[str, Scalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "aliases", tuple(self.aliases))
        object.__setattr__(self, "attributes", _readonly_mapping(self.attributes))


@dataclass(frozen=True, slots=True)
class Record:
    id: str
    name: str | None = None
    attributes: Mapping[str, Scalar] = field(default_factory=dict)
    applicable: bool = True
    not_applicable_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _readonly_mapping(self.attributes))


@dataclass(frozen=True, slots=True)
class NormalizationConfig:
    case_fold: bool
    punctuation: Literal["preserve", "remove", "space"]


@dataclass(frozen=True, slots=True)
class CandidateRule:
    id: str
    type: CandidateRuleType
    entity_field: str | None = None
    record_field: str | None = None


@dataclass(frozen=True, slots=True)
class EqualConstraint:
    id: str
    entity_field: str
    record_field: str
    missing: MissingBehavior


@dataclass(frozen=True, slots=True)
class Override:
    record_id: str
    status: OverrideStatus
    reason: str
    entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class LinkageConfig:
    normalization: NormalizationConfig
    candidate_rules: tuple[CandidateRule, ...]
    apply_overrides: bool
    constraints: tuple[EqualConstraint, ...] = ()
    overrides: tuple[Override, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_rules", tuple(self.candidate_rules))
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "overrides", tuple(self.overrides))


@dataclass(frozen=True, slots=True)
class Evidence:
    rule_id: str
    phase: EvidencePhase
    outcome: str
    entity_id: str | None = None
    details: Mapping[str, EvidenceValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _readonly_mapping(self.details))


@dataclass(frozen=True, slots=True)
class LinkageResult:
    record_id: str
    status: LinkageStatus
    entity_id: str | None
    candidate_entity_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    normalized_record_name: str | None
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_entity_ids", tuple(sorted(self.candidate_entity_ids)))
        object.__setattr__(self, "reason_codes", tuple(sorted(self.reason_codes)))
        object.__setattr__(self, "evidence", tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class AuditSummary:
    status_counts: Mapping[LinkageStatus, int]
    reason_code_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "status_counts",
            MappingProxyType(dict(sorted(self.status_counts.items()))),
        )
        object.__setattr__(
            self,
            "reason_code_counts",
            MappingProxyType(dict(sorted(self.reason_code_counts.items()))),
        )
