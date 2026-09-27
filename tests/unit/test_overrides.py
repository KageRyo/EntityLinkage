from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from entitylinkage.config import load_config
from entitylinkage.errors import ConfigError
from entitylinkage.matcher import Linker


def _config(
    *, enabled: bool = True, records: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "version": 1,
        "entities": [{"id": "entity-1", "name": "Known Entity"}],
        "records": records if records is not None else [{"id": "record-1", "name": "Unknown"}],
        "matching": {
            "normalization": {"case_fold": True, "punctuation": "preserve"},
            "candidate_rules": [{"id": "name", "type": "normalized_name"}],
            "apply_overrides": enabled,
        },
        "overrides": [
            {
                "record_id": "record-1",
                "status": "resolved",
                "entity_id": "entity-1",
                "reason": "reviewed_identity_match",
            }
        ],
    }


def _load(tmp_path: Path, data: dict[str, object]):
    path = tmp_path / "entitylinkage.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return load_config(path)


def test_disabled_overrides_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="apply_overrides"):
        _load(tmp_path, _config(enabled=False))


def test_resolved_override_takes_precedence_and_preserves_review_reason(tmp_path: Path) -> None:
    loaded = _load(tmp_path, _config())

    (result,) = Linker(loaded.config).link(loaded.entities, loaded.records)

    assert result.status == "resolved"
    assert result.entity_id == "entity-1"
    assert result.reason_codes == ("reviewed_identity_match",)
    assert len(result.evidence) == 1
    assert result.evidence[0].phase == "override"
    assert result.evidence[0].outcome == "resolved"
    assert result.evidence[0].details["reason"] == "reviewed_identity_match"


def test_not_applicable_override_has_no_entity_id(tmp_path: Path) -> None:
    data = _config()
    data["overrides"] = [
        {"record_id": "record-1", "status": "not_applicable", "reason": "out_of_scope"}
    ]
    loaded = _load(tmp_path, data)

    (result,) = Linker(loaded.config).link(loaded.entities, loaded.records)

    assert result.status == "not_applicable"
    assert result.entity_id is None
    assert result.candidate_entity_ids == ()
    assert result.reason_codes == ("out_of_scope",)


@pytest.mark.parametrize(
    "override, message",
    [
        (
            {
                "record_id": "unknown",
                "status": "resolved",
                "entity_id": "entity-1",
                "reason": "reviewed",
            },
            "record",
        ),
        (
            {
                "record_id": "record-1",
                "status": "resolved",
                "entity_id": "unknown",
                "reason": "reviewed",
            },
            "entity",
        ),
        (
            {
                "record_id": "record-1",
                "status": "resolved",
                "entity_id": "entity-1",
                "reason": "Bad Code",
            },
            "reason",
        ),
        (
            {"record_id": "record-1", "status": "resolved", "reason": "reviewed"},
            "entity_id",
        ),
        (
            {
                "record_id": "record-1",
                "status": "not_applicable",
                "entity_id": "entity-1",
                "reason": "out_of_scope",
            },
            "entity_id",
        ),
    ],
    ids=[
        "unknown-record",
        "unknown-entity",
        "malformed-reason",
        "missing-entity",
        "unexpected-entity",
    ],
)
def test_rejects_invalid_override_declarations(tmp_path: Path, override, message: str) -> None:
    data = _config()
    data["overrides"] = [override]

    with pytest.raises(ConfigError, match=message):
        _load(tmp_path, data)


def test_override_cannot_contradict_explicit_not_applicable_record(tmp_path: Path) -> None:
    data = _config(
        records=[{"id": "record-1", "applicable": False, "not_applicable_reason": "out_of_scope"}]
    )

    with pytest.raises(ConfigError, match="not applicable"):
        _load(tmp_path, data)
