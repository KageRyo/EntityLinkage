from dataclasses import FrozenInstanceError

import pytest

from entitylinkage.model import (
    AuditSummary,
    CandidateRule,
    Entity,
    EqualConstraint,
    Evidence,
    LinkageConfig,
    LinkageResult,
    NormalizationConfig,
    Override,
    Record,
)


def test_models_represent_generic_linkage_inputs_and_results() -> None:
    normalization = NormalizationConfig(case_fold=True, punctuation="preserve")
    candidate = CandidateRule(
        id="publisher-id",
        type="exact_value",
        entity_field="attributes.publisher_id",
        record_field="attributes.publisher_id",
    )
    constraint = EqualConstraint(
        id="same-year",
        entity_field="attributes.year",
        record_field="attributes.year",
        missing="ignore",
    )
    override = Override(
        record_id="record-1",
        status="resolved",
        reason="reviewed_identity_match",
        entity_id="entity-1",
    )
    config = LinkageConfig(
        normalization=normalization,
        candidate_rules=(candidate,),
        apply_overrides=True,
        constraints=(constraint,),
        overrides=(override,),
    )
    entity = Entity(
        id="entity-1",
        name="Example Catalog",
        aliases=("Catalog Example",),
        attributes={"publisher_id": "pub-7", "year": 2024},
    )
    record = Record(
        id="record-1",
        name="Catalog Example",
        attributes={"publisher_id": "pub-7", "year": 2024},
    )
    evidence = Evidence(
        rule_id="publisher-id",
        phase="candidate",
        outcome="match",
        entity_id="entity-1",
        details={"record_value": "pub-7"},
    )
    result = LinkageResult(
        record_id="record-1",
        status="resolved",
        entity_id="entity-1",
        candidate_entity_ids=("entity-1",),
        reason_codes=(),
        normalized_record_name="catalog example",
        evidence=(evidence,),
    )
    summary = AuditSummary(
        status_counts={
            "resolved": 1,
            "ambiguous": 0,
            "unresolved": 0,
            "not_applicable": 0,
        },
        reason_code_counts={},
    )

    assert config.candidate_rules == (candidate,)
    assert entity.attributes["publisher_id"] == "pub-7"
    assert record.attributes["year"] == 2024
    assert result.candidate_entity_ids == ("entity-1",)
    assert summary.status_counts["resolved"] == 1


def test_models_are_frozen_and_copy_attribute_mappings() -> None:
    attributes = {"year": 2024}
    entity = Entity(id="entity-1", name="Example", attributes=attributes)
    details = {"record_value": "Example"}
    evidence = Evidence(
        rule_id="name",
        phase="candidate",
        outcome="match",
        entity_id="entity-1",
        details=details,
    )

    attributes["year"] = 2025
    details["record_value"] = "Changed"

    assert entity.attributes["year"] == 2024
    assert evidence.details["record_value"] == "Example"
    with pytest.raises(TypeError):
        entity.attributes["year"] = 2026
    with pytest.raises(TypeError):
        evidence.details["record_value"] = "Changed again"
    with pytest.raises(FrozenInstanceError):
        entity.name = "Changed"
