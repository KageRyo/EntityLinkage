from __future__ import annotations

import re
from pathlib import Path

from entitylinkage.audit import audit_results
from entitylinkage.config import load_config
from entitylinkage.matcher import Linker
from entitylinkage.model import LinkageConfig

EXAMPLES = Path(__file__).parents[2] / "examples"


def _run_example(name: str):
    loaded = load_config(EXAMPLES / name)
    return loaded, Linker(loaded.config).link(loaded.entities, loaded.records)


def test_basic_example_has_exact_statuses_and_candidates() -> None:
    _, results = _run_example("basic")

    assert [result.status for result in results] == [
        "resolved",
        "ambiguous",
        "unresolved",
        "not_applicable",
    ]
    assert results[0].entity_id == "product-001"
    assert results[1].candidate_entity_ids == ("product-001", "product-002")
    assert results[1].reason_codes == ("multiple_valid_candidates",)
    assert results[2].reason_codes == ("no_identity_candidate",)
    assert results[3].reason_codes == ("outside_catalog_scope",)
    assert dict(audit_results(results).status_counts) == {
        "ambiguous": 1,
        "not_applicable": 1,
        "resolved": 1,
        "unresolved": 1,
    }


def test_ambiguous_example_isolates_a_shared_alias() -> None:
    _, results = _run_example("ambiguous")

    assert len(results) == 1
    assert results[0].status == "ambiguous"
    assert results[0].entity_id is None
    assert results[0].candidate_entity_ids == ("product-010", "product-011")


def test_manual_review_example_resolves_only_through_enabled_override() -> None:
    loaded, results = _run_example("manual-review")

    assert loaded.config.apply_overrides is True
    assert results[0].status == "resolved"
    assert results[0].entity_id == "product-020"
    assert results[0].reason_codes == ("reviewed_identity_match",)
    without_overrides = LinkageConfig(
        normalization=loaded.config.normalization,
        candidate_rules=loaded.config.candidate_rules,
        apply_overrides=False,
        constraints=loaded.config.constraints,
    )
    (automatic_result,) = Linker(without_overrides).link(loaded.entities, loaded.records)
    assert automatic_result.status == "unresolved"


def test_example_labels_and_identifiers_are_fictional_catalog_values() -> None:
    for example in ("basic", "ambiguous", "manual-review"):
        loaded = load_config(EXAMPLES / example)
        for entity in loaded.entities:
            assert "fictional" in entity.name.casefold()
            assert all("fictional" in alias.casefold() for alias in entity.aliases)
            assert re.fullmatch(r"product-\d{3}", entity.id)
        for record in loaded.records:
            assert record.name is None or "fictional" in record.name.casefold()
            assert re.fullmatch(r"source-record-\d{3}", record.id)
