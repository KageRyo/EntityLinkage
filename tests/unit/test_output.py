from __future__ import annotations

import csv
import io
import json
import unicodedata
from pathlib import Path

import pytest

from entitylinkage import Linker, __version__
from entitylinkage.model import (
    CandidateRule,
    Entity,
    Evidence,
    LinkageConfig,
    LinkageResult,
    NormalizationConfig,
    Record,
)
from entitylinkage.output import (
    inspection_payload,
    serialize_linkage_csv,
    serialize_linkage_json,
    serialize_summary_json,
    write_artifacts,
)


CSV_FIELDS = "record_id,status,entity_id,candidate_entity_ids,reason_codes,evidence"


def _config() -> LinkageConfig:
    return LinkageConfig(
        normalization=NormalizationConfig(case_fold=True, punctuation="preserve"),
        candidate_rules=(CandidateRule(id="name", type="normalized_name"),),
        apply_overrides=False,
    )


def _result(
    *,
    evidence: tuple[Evidence, ...] = (),
    record_id: str = "record-1",
    status: str = "resolved",
) -> LinkageResult:
    entity_id = "entity-1" if status == "resolved" else None
    return LinkageResult(
        record_id=record_id,
        status=status,
        entity_id=entity_id,
        candidate_entity_ids=(entity_id,) if entity_id else (),
        reason_codes=() if status == "resolved" else ("no_identity_candidate",),
        normalized_record_name="alpha" if record_id == "record-1" else None,
        evidence=evidence,
    )


def test_serializers_are_stable_sorted_and_include_runtime_metadata(tmp_path: Path) -> None:
    results = (_result(record_id="record-2", status="unresolved"), _result())

    linkage = serialize_linkage_json(results)
    summary = serialize_summary_json(results)
    csv_text = serialize_linkage_csv(results)
    parsed_linkage = json.loads(linkage)
    parsed_summary = json.loads(summary)

    assert linkage == serialize_linkage_json(tuple(reversed(results)))
    assert summary == serialize_summary_json(tuple(reversed(results)))
    assert csv_text == serialize_linkage_csv(tuple(reversed(results)))
    assert [item["record_id"] for item in parsed_linkage["results"]] == ["record-1", "record-2"]
    assert parsed_linkage["schema_version"] == "entitylinkage-results-v1"
    assert parsed_linkage["tool_version"] == __version__
    assert parsed_linkage["unicode_version"] == unicodedata.unidata_version
    assert parsed_summary["schema_version"] == "entitylinkage-results-v1"
    assert parsed_summary["tool_version"] == __version__
    assert parsed_summary["unicode_version"] == unicodedata.unidata_version
    assert "timestamp" not in linkage.lower()
    assert str(tmp_path) not in linkage + summary + csv_text
    assert "path" not in parsed_linkage
    assert "path" not in parsed_summary
    assert csv_text.splitlines()[0] == CSV_FIELDS


def test_csv_round_trip_preserves_structured_evidence_and_lf_lines() -> None:
    evidence = Evidence(
        rule_id="source-note",
        phase="candidate",
        outcome="match",
        entity_id="entity-1",
        details={"note": 'comma, quote " and newline\nremain intact'},
    )
    csv_text = serialize_linkage_csv((_result(evidence=(evidence,)),))
    parsed = next(csv.DictReader(io.StringIO(csv_text, newline="")))

    assert "\r" not in csv_text
    assert csv_text.endswith("\n")
    assert json.loads(parsed["evidence"]) == [
        {
            "details": {"note": 'comma, quote " and newline\nremain intact'},
            "entity_id": "entity-1",
            "outcome": "match",
            "phase": "candidate",
            "rule_id": "source-note",
        }
    ]


def test_json_rejects_non_finite_evidence_values() -> None:
    result = _result(
        evidence=(Evidence("external", "candidate", "match", details={"value": float("nan")}),)
    )

    with pytest.raises(ValueError, match="Out of range float values"):
        serialize_linkage_json((result,))


def test_linkage_serialization_is_independent_of_alias_order() -> None:
    linker = Linker(_config())
    record = Record(id="record-1", name="Preferred Label")
    first_entity = Entity(id="entity-1", name="Catalog", aliases=("Preferred Label", "Other"))
    second_entity = Entity(id="entity-1", name="Catalog", aliases=("Other", "Preferred Label"))

    first_results = linker.link((first_entity,), (record,))
    second_results = linker.link((second_entity,), (record,))

    assert serialize_linkage_json(first_results) == serialize_linkage_json(second_results)
    assert serialize_linkage_csv(first_results) == serialize_linkage_csv(second_results)


def test_inspection_payload_exposes_record_normalization_evidence_and_decision() -> None:
    record = Record(id="record-1", name="Alpha", attributes={"year": 2024})
    (result,) = Linker(_config()).link((Entity(id="entity-1", name="Alpha"),), (record,))

    payload = inspection_payload(record, result)

    assert payload["record"] == {
        "id": "record-1",
        "name": "Alpha",
        "attributes": {"year": 2024},
        "applicable": True,
        "not_applicable_reason": None,
    }
    assert payload["normalized_record_name"] == "alpha"
    assert payload["evidence"][0]["phase"] == "candidate"
    assert payload["result"] == {
        "status": "resolved",
        "entity_id": "entity-1",
        "candidate_entity_ids": ["entity-1"],
        "reason_codes": [],
    }


def test_write_artifacts_creates_three_deterministic_files(tmp_path: Path) -> None:
    results = (_result(),)

    write_artifacts(results, tmp_path / "reports")

    assert (tmp_path / "reports" / "linkage.json").read_text(
        encoding="utf-8"
    ) == serialize_linkage_json(results)
    assert (tmp_path / "reports" / "linkage.csv").read_text(
        encoding="utf-8"
    ) == serialize_linkage_csv(results)
    assert (tmp_path / "reports" / "summary.json").read_text(
        encoding="utf-8"
    ) == serialize_summary_json(results)
