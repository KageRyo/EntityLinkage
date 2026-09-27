from __future__ import annotations

import csv
import io
import json
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from entitylinkage import __version__
from entitylinkage.audit import audit_results
from entitylinkage.model import Evidence, EvidenceValue, LinkageResult, Record

_SCHEMA_VERSION = "entitylinkage-results-v1"
_CSV_FIELDS = (
    "record_id",
    "status",
    "entity_id",
    "candidate_entity_ids",
    "reason_codes",
    "evidence",
)


def serialize_linkage_json(results: Sequence[LinkageResult]) -> str:
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "tool_version": __version__,
        "unicode_version": unicodedata.unidata_version,
        "results": _result_objects(results),
    }
    return _canonical_json(payload)


def serialize_summary_json(results: Sequence[LinkageResult]) -> str:
    summary = audit_results(results)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "tool_version": __version__,
        "unicode_version": unicodedata.unidata_version,
        "status_counts": dict(summary.status_counts),
        "reason_code_counts": dict(summary.reason_code_counts),
    }
    return _canonical_json(payload)


def serialize_linkage_csv(results: Sequence[LinkageResult]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(_CSV_FIELDS)
    for result in _result_objects(results):
        writer.writerow(
            (
                result["record_id"],
                result["status"],
                result["entity_id"] or "",
                _canonical_json(result["candidate_entity_ids"]),
                _canonical_json(result["reason_codes"]),
                _canonical_json(result["evidence"]),
            )
        )
    return stream.getvalue()


def inspection_payload(record: Record, result: LinkageResult) -> dict[str, object]:
    """Build a stable JSON-ready view of one record and its linkage decision."""
    return {
        "record": {
            "id": record.id,
            "name": record.name,
            "attributes": dict(sorted(record.attributes.items())),
            "applicable": record.applicable,
            "not_applicable_reason": record.not_applicable_reason,
        },
        "normalized_record_name": result.normalized_record_name,
        "evidence": _evidence_objects(result.evidence),
        "result": {
            "status": result.status,
            "entity_id": result.entity_id,
            "candidate_entity_ids": list(result.candidate_entity_ids),
            "reason_codes": list(result.reason_codes),
        },
    }


def write_artifacts(results: Sequence[LinkageResult], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "linkage.json").write_bytes(serialize_linkage_json(results).encode("utf-8"))
    (output_dir / "linkage.csv").write_bytes(serialize_linkage_csv(results).encode("utf-8"))
    (output_dir / "summary.json").write_bytes(serialize_summary_json(results).encode("utf-8"))


def _result_objects(results: Sequence[LinkageResult]) -> list[dict[str, object]]:
    objects = [
        {
            "record_id": result.record_id,
            "status": result.status,
            "entity_id": result.entity_id,
            "candidate_entity_ids": list(sorted(result.candidate_entity_ids)),
            "reason_codes": list(sorted(result.reason_codes)),
            "normalized_record_name": result.normalized_record_name,
            "evidence": _evidence_objects(result.evidence),
        }
        for result in results
    ]
    return sorted(objects, key=lambda item: (item["record_id"], _canonical_json(item)))


def _evidence_objects(evidence: Sequence[Evidence]) -> list[dict[str, object]]:
    objects = [
        {
            "rule_id": item.rule_id,
            "phase": item.phase,
            "outcome": item.outcome,
            "entity_id": item.entity_id,
            "details": {key: _json_value(value) for key, value in item.details.items()},
        }
        for item in evidence
    ]
    return sorted(
        objects,
        key=lambda item: (
            item["phase"],
            item["rule_id"],
            item["entity_id"] or "",
            item["outcome"],
            _canonical_json(item["details"]),
        ),
    )


def _json_value(value: EvidenceValue) -> Any:
    return list(value) if isinstance(value, tuple) else value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
