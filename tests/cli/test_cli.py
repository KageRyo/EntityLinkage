from __future__ import annotations

import json
from pathlib import Path

import yaml

from entitylinkage.cli import main


def _config(*, ambiguous: bool = False, unresolved: bool = False) -> dict[str, object]:
    entities: list[dict[str, object]] = [
        {"id": "entity-1", "name": "Catalog One", "aliases": ["Shared Label"]}
    ]
    if ambiguous:
        entities.append({"id": "entity-2", "name": "Catalog Two", "aliases": ["Shared Label"]})
    records: list[dict[str, object]] = [{"id": "record-1", "name": "Shared Label"}]
    if unresolved:
        records.append({"id": "record-2", "name": "Unknown"})
    return {
        "version": 1,
        "entities": entities,
        "records": records,
        "matching": {
            "normalization": {"case_fold": True, "punctuation": "preserve"},
            "candidate_rules": [{"id": "name", "type": "normalized_name"}],
            "apply_overrides": False,
        },
    }


def _write_config(tmp_path: Path, data: dict[str, object]) -> Path:
    config = tmp_path / "entitylinkage.yaml"
    config.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return config


def test_validate_prints_a_success_report(tmp_path: Path, capsys) -> None:
    config = _write_config(tmp_path, _config())

    status = main(["validate", str(config)])

    report = json.loads(capsys.readouterr().out)
    assert status == 0
    assert report == {"entities": 1, "records": 1, "valid": True}


def test_link_writes_artifacts_and_prints_summary(tmp_path: Path, capsys) -> None:
    config = _write_config(tmp_path, _config(unresolved=True))
    output = tmp_path / "out"

    status = main(["link", str(config), "--output", str(output)])

    summary = json.loads(capsys.readouterr().out)
    assert status == 0
    assert {path.name for path in output.iterdir()} == {
        "linkage.json",
        "linkage.csv",
        "summary.json",
    }
    assert summary["status_counts"]["resolved"] == 1
    assert summary["status_counts"]["unresolved"] == 1


def test_link_defaults_to_entitylinkage_output_directory(tmp_path: Path, monkeypatch) -> None:
    config = _write_config(tmp_path, _config())
    monkeypatch.chdir(tmp_path)

    status = main(["link", str(config)])

    assert status == 0
    assert (tmp_path / "entitylinkage-output" / "linkage.json").is_file()


def test_audit_returns_one_for_ambiguous_or_unresolved_records(tmp_path: Path, capsys) -> None:
    config = _write_config(tmp_path, _config(ambiguous=True, unresolved=True))

    status = main(["audit", str(config)])

    report = json.loads(capsys.readouterr().out)
    assert status == 1
    assert report["status_counts"]["ambiguous"] == 1
    assert report["status_counts"]["unresolved"] == 1


def test_audit_returns_zero_for_resolved_and_not_applicable_records(tmp_path: Path, capsys) -> None:
    data = _config()
    data["records"].append(
        {
            "id": "record-outside",
            "applicable": False,
            "not_applicable_reason": "outside_scope",
        }
    )
    config = _write_config(tmp_path, data)

    status = main(["audit", str(config)])

    report = json.loads(capsys.readouterr().out)
    assert status == 0
    assert report["status_counts"]["resolved"] == 1
    assert report["status_counts"]["not_applicable"] == 1


def test_inspect_prints_record_normalization_evidence_and_result(tmp_path: Path, capsys) -> None:
    config = _write_config(tmp_path, _config())

    status = main(["inspect", "record-1", str(config)])

    report = json.loads(capsys.readouterr().out)
    assert status == 0
    assert report["record"]["id"] == "record-1"
    assert report["normalized_record_name"] == "shared label"
    assert report["evidence"][0]["phase"] == "candidate"
    assert report["result"]["status"] == "resolved"


def test_unknown_record_id_returns_two_and_writes_to_stderr(tmp_path: Path, capsys) -> None:
    config = _write_config(tmp_path, _config())

    status = main(["inspect", "missing-record", str(config)])

    assert status == 2
    assert "unknown record" in capsys.readouterr().err


def test_malformed_configuration_returns_two_and_writes_to_stderr(tmp_path: Path, capsys) -> None:
    config = tmp_path / "invalid.yaml"
    config.write_text("version: 2\nentities: []\nrecords: []\nmatching: {}\n", encoding="utf-8")

    status = main(["validate", str(config)])

    assert status == 2
    assert "version" in capsys.readouterr().err
