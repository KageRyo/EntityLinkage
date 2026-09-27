import pytest

from entitylinkage import Linker
from entitylinkage.errors import ConfigError
from entitylinkage.model import (
    CandidateRule,
    Entity,
    EqualConstraint,
    LinkageConfig,
    NormalizationConfig,
    Record,
)


def _name_config(*, constraints: tuple[EqualConstraint, ...] = ()) -> LinkageConfig:
    return LinkageConfig(
        normalization=NormalizationConfig(case_fold=True, punctuation="preserve"),
        candidate_rules=(CandidateRule(id="name", type="normalized_name"),),
        apply_overrides=False,
        constraints=constraints,
    )


def test_alias_and_equal_constraint_resolve_with_explainable_evidence() -> None:
    year = EqualConstraint(
        id="same-year",
        entity_field="attributes.year",
        record_field="attributes.year",
        missing="ignore",
    )
    linker = Linker(_name_config(constraints=(year,)))
    entities = (
        Entity(
            id="entity-002",
            name="Second Catalog",
            aliases=("Shared Catalog",),
            attributes={"year": 2025},
        ),
        Entity(
            id="entity-001",
            name="First Catalog",
            aliases=("Shared Catalog",),
            attributes={"year": 2024},
        ),
    )
    record = Record(id="record-1", name="Shared Catalog", attributes={"year": 2024})

    (result,) = linker.link(entities, (record,))

    assert result.status == "resolved"
    assert result.entity_id == "entity-001"
    assert result.candidate_entity_ids == ("entity-001",)
    assert result.normalized_record_name == "shared catalog"
    assert any(
        item.phase == "candidate"
        and item.entity_id == "entity-001"
        and item.details["matched_label"] == "alias"
        for item in result.evidence
    )
    assert {
        (item.entity_id, item.outcome) for item in result.evidence if item.phase == "constraint"
    } == {
        ("entity-001", "match"),
        ("entity-002", "mismatch"),
    }


def test_exact_publisher_id_rule_can_generate_candidates() -> None:
    rule = CandidateRule(
        id="publisher-id",
        type="exact_value",
        entity_field="attributes.publisher_id",
        record_field="attributes.publisher_id",
    )
    config = LinkageConfig(
        normalization=NormalizationConfig(case_fold=True, punctuation="preserve"),
        candidate_rules=(rule,),
        apply_overrides=False,
    )
    entity = Entity(id="entity-1", name="Catalog", attributes={"publisher_id": "pub-7"})
    record = Record(id="record-1", attributes={"publisher_id": "pub-7"})

    (result,) = Linker(config).link((entity,), (record,))

    assert result.status == "resolved"
    assert result.entity_id == "entity-1"
    assert result.evidence[0].rule_id == "publisher-id"
    assert result.evidence[0].outcome == "match"


def test_two_candidates_are_ambiguous_and_sorted() -> None:
    entities = (
        Entity(id="entity-z", name="Catalog Z", aliases=("Shared",)),
        Entity(id="entity-a", name="Catalog A", aliases=("Shared",)),
    )
    record = Record(id="record-1", name="Shared")

    (result,) = Linker(_name_config()).link(entities, (record,))

    assert result.status == "ambiguous"
    assert result.entity_id is None
    assert result.candidate_entity_ids == ("entity-a", "entity-z")
    assert result.reason_codes == ("multiple_valid_candidates",)


def test_adding_a_second_valid_candidate_changes_resolved_to_ambiguous() -> None:
    linker = Linker(_name_config())
    record = Record(id="record-1", name="Shared")
    first = Entity(id="entity-1", name="Catalog One", aliases=("Shared",))
    second = Entity(id="entity-2", name="Catalog Two", aliases=("Shared",))

    (resolved,) = linker.link((first,), (record,))
    (ambiguous,) = linker.link((first, second), (record,))

    assert resolved.status == "resolved"
    assert ambiguous.status == "ambiguous"
    assert ambiguous.entity_id is None


@pytest.mark.parametrize(
    "entities",
    [
        (
            Entity(id="same", name="Wrong", attributes={"year": 2024}),
            Entity(id="same", name="Target", attributes={"year": 2025}),
        ),
        (
            Entity(id="same", name="Target", attributes={"year": 2025}),
            Entity(id="same", name="Wrong", attributes={"year": 2024}),
        ),
    ],
    ids=["conflicting-entity-order", "reversed-conflicting-entity-order"],
)
def test_duplicate_entity_ids_are_rejected_before_matching(entities: tuple[Entity, ...]) -> None:
    year = EqualConstraint(
        id="same-year",
        entity_field="attributes.year",
        record_field="attributes.year",
        missing="reject",
    )
    record = Record(id="record-1", name="Target", attributes={"year": 2024})

    with pytest.raises(ConfigError, match="duplicate entity ID"):
        Linker(_name_config(constraints=(year,))).link(entities, (record,))


def test_duplicate_record_ids_are_rejected_before_matching() -> None:
    entity = Entity(id="entity-1", name="Shared")
    record = Record(id="record-1", name="Shared")

    with pytest.raises(ConfigError, match="duplicate record ID"):
        Linker(_name_config()).link((entity,), (record, record))


def test_candidate_rules_union_support_from_distinct_identity_fields() -> None:
    config = LinkageConfig(
        normalization=NormalizationConfig(case_fold=True, punctuation="preserve"),
        candidate_rules=(
            CandidateRule(id="name", type="normalized_name"),
            CandidateRule(
                id="external-id",
                type="exact_value",
                entity_field="attributes.external_id",
                record_field="attributes.external_id",
            ),
        ),
        apply_overrides=False,
    )
    entities = (
        Entity(id="entity-1", name="Name Match", attributes={"external_id": "one"}),
        Entity(
            id="entity-2", name="Other", aliases=("Name Match",), attributes={"external_id": "two"}
        ),
    )
    record = Record(id="record-1", name="Name Match", attributes={"external_id": "one"})

    (result,) = Linker(config).link(entities, (record,))

    assert result.status == "ambiguous"
    assert result.candidate_entity_ids == ("entity-1", "entity-2")


def test_empty_identity_value_never_generates_a_candidate() -> None:
    rule = CandidateRule(
        id="publisher-id",
        type="exact_value",
        entity_field="attributes.publisher_id",
        record_field="attributes.publisher_id",
    )
    config = LinkageConfig(
        normalization=NormalizationConfig(case_fold=True, punctuation="preserve"),
        candidate_rules=(rule,),
        apply_overrides=False,
    )
    entity = Entity(id="entity-1", name="Catalog", attributes={"publisher_id": ""})
    record = Record(id="record-1", attributes={"publisher_id": ""})

    (result,) = Linker(config).link((entity,), (record,))

    assert result.status == "unresolved"
    assert result.candidate_entity_ids == ()


def test_missing_ignore_leaves_candidate_without_claiming_attribute_match() -> None:
    year = EqualConstraint("year", "attributes.year", "attributes.year", missing="ignore")
    entity = Entity(id="entity-1", name="Catalog", aliases=("Shared",), attributes={"year": 2024})
    record = Record(id="record-1", name="Shared")

    (result,) = Linker(_name_config(constraints=(year,))).link((entity,), (record,))

    assert result.status == "resolved"
    assert result.entity_id == "entity-1"
    assert any(item.outcome == "missing_ignored" for item in result.evidence)
    assert not any(
        item.phase == "constraint" and item.outcome == "match" for item in result.evidence
    )


def test_missing_reject_removes_candidate() -> None:
    year = EqualConstraint("year", "attributes.year", "attributes.year", missing="reject")
    entity = Entity(id="entity-1", name="Catalog", aliases=("Shared",), attributes={"year": 2024})
    record = Record(id="record-1", name="Shared")

    (result,) = Linker(_name_config(constraints=(year,))).link((entity,), (record,))

    assert result.status == "unresolved"
    assert result.candidate_entity_ids == ()
    assert result.reason_codes == ("insufficient_metadata",)


def test_conflicting_attribute_constraint_rejects_candidate() -> None:
    year = EqualConstraint("year", "attributes.year", "attributes.year", missing="ignore")
    entity = Entity(id="entity-1", name="Catalog", aliases=("Shared",), attributes={"year": 2024})
    record = Record(id="record-1", name="Shared", attributes={"year": 2025})

    (result,) = Linker(_name_config(constraints=(year,))).link((entity,), (record,))

    assert result.status == "unresolved"
    assert result.candidate_entity_ids == ()
    assert result.reason_codes == ("attribute_conflict",)


def test_record_marked_not_applicable_is_not_linked() -> None:
    entity = Entity(id="entity-1", name="Shared")
    record = Record(
        id="record-1",
        name="Shared",
        applicable=False,
        not_applicable_reason="outside_reference_scope",
    )

    (result,) = Linker(_name_config()).link((entity,), (record,))

    assert result.status == "not_applicable"
    assert result.entity_id is None
    assert result.candidate_entity_ids == ()
    assert result.reason_codes == ("outside_reference_scope",)


def test_results_are_sorted_by_record_id_independent_of_input_order() -> None:
    entities = (Entity(id="entity-1", name="Alpha"), Entity(id="entity-2", name="Beta"))
    records = (Record(id="record-z", name="Beta"), Record(id="record-a", name="Alpha"))

    results = Linker(_name_config()).link(entities, records)

    assert [item.record_id for item in results] == ["record-a", "record-z"]


def test_equal_constraint_is_type_sensitive() -> None:
    enabled = EqualConstraint(
        "enabled", "attributes.enabled", "attributes.enabled", missing="ignore"
    )
    entity = Entity(id="entity-1", name="Catalog", attributes={"enabled": False})
    record = Record(id="record-1", name="Catalog", attributes={"enabled": 0})

    (result,) = Linker(_name_config(constraints=(enabled,))).link((entity,), (record,))

    assert result.status == "unresolved"
    assert result.reason_codes == ("attribute_conflict",)


def test_empty_constraint_value_is_present() -> None:
    code = EqualConstraint("code", "attributes.code", "attributes.code", missing="reject")
    entity = Entity(id="entity-1", name="Catalog", attributes={"code": ""})
    record = Record(id="record-1", name="Catalog", attributes={"code": ""})

    (result,) = Linker(_name_config(constraints=(code,))).link((entity,), (record,))

    assert result.status == "resolved"
    assert any(item.phase == "constraint" and item.outcome == "match" for item in result.evidence)


def test_all_identity_inputs_missing_is_insufficient_metadata() -> None:
    config = LinkageConfig(
        normalization=NormalizationConfig(case_fold=True, punctuation="preserve"),
        candidate_rules=(
            CandidateRule(id="name", type="normalized_name"),
            CandidateRule(
                id="publisher-id",
                type="exact_value",
                entity_field="attributes.publisher_id",
                record_field="attributes.publisher_id",
            ),
        ),
        apply_overrides=False,
    )
    entity = Entity(id="entity-1", name="Catalog", attributes={"publisher_id": "pub-7"})
    record = Record(id="record-1")

    (result,) = Linker(config).link((entity,), (record,))

    assert result.status == "unresolved"
    assert result.reason_codes == ("insufficient_metadata",)


def test_usable_unmatched_identity_is_no_identity_candidate() -> None:
    entity = Entity(id="entity-1", name="Catalog")
    record = Record(id="record-1", name="Unlisted Publication")

    (result,) = Linker(_name_config()).link((entity,), (record,))

    assert result.status == "unresolved"
    assert result.reason_codes == ("no_identity_candidate",)
    assert result.evidence[0].details["entity_values"] == ("catalog",)
