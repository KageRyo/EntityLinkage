from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from entitylinkage.config import LinkageInput, load_config
from entitylinkage.errors import ConfigError


def _minimal_config() -> dict[str, object]:
    return {
        "version": 1,
        "entities": [{"id": "entity-1", "name": "Alpha"}],
        "records": [{"id": "record-1", "name": "Alpha"}],
        "matching": {
            "normalization": {"case_fold": True, "punctuation": "preserve"},
            "candidate_rules": [{"id": "name", "type": "normalized_name"}],
            "apply_overrides": False,
        },
    }


def _write_config(tmp_path: Path, data: dict[str, object]) -> Path:
    path = tmp_path / "entitylinkage.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_loads_valid_configuration_file_and_directory(tmp_path: Path) -> None:
    path = _write_config(tmp_path, _minimal_config())

    loaded_from_file = load_config(path)
    loaded_from_directory = load_config(tmp_path)

    assert isinstance(loaded_from_file, LinkageInput)
    assert loaded_from_file == loaded_from_directory
    assert loaded_from_file.entities[0].id == "entity-1"
    assert loaded_from_file.records[0].id == "record-1"
    assert loaded_from_file.config.apply_overrides is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.pop("version"),
        lambda data: data.update(version=2),
        lambda data: data.update(version=True),
        lambda data: data["matching"].update(
            normalization={"case_fold": True, "punctuation": "hyphen"}
        ),
        lambda data: data["matching"].update(
            normalization={"case_fold": 1, "punctuation": "space"}
        ),
        lambda data: data["matching"].update(candidate_rules=[]),
        lambda data: data["matching"].update(apply_overrides="false"),
    ],
    ids=[
        "required-version",
        "unsupported-version",
        "boolean-version",
        "unsupported-punctuation",
        "boolean-case-fold",
        "nonempty-candidate-rules",
        "boolean-apply-overrides",
    ],
)
def test_rejects_invalid_required_settings(tmp_path: Path, mutate) -> None:
    data = _minimal_config()
    mutate(data)

    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, data))


@pytest.mark.parametrize(
    "collection, duplicate_item",
    [
        ("entities", {"id": "entity-1", "name": "Beta"}),
        ("records", {"id": "record-1", "name": "Beta"}),
    ],
)
def test_rejects_duplicate_entity_and_record_ids(
    tmp_path: Path, collection: str, duplicate_item: dict[str, str]
) -> None:
    data = _minimal_config()
    data[collection].append(duplicate_item)

    with pytest.raises(ConfigError, match="duplicate"):
        load_config(_write_config(tmp_path, data))


def test_rejects_duplicate_rule_ids(tmp_path: Path) -> None:
    data = _minimal_config()
    data["matching"]["candidate_rules"].append({"id": "name", "type": "normalized_name"})

    with pytest.raises(ConfigError, match="duplicate"):
        load_config(_write_config(tmp_path, data))


def test_rejects_duplicate_override_record_ids(tmp_path: Path) -> None:
    data = _minimal_config()
    data["matching"]["apply_overrides"] = True
    data["overrides"] = [
        {
            "record_id": "record-1",
            "status": "resolved",
            "entity_id": "entity-1",
            "reason": "reviewed",
        },
        {
            "record_id": "record-1",
            "status": "resolved",
            "entity_id": "entity-1",
            "reason": "reviewed",
        },
    ]

    with pytest.raises(ConfigError, match="duplicate"):
        load_config(_write_config(tmp_path, data))


def test_rejects_duplicate_normalized_labels_within_an_entity(tmp_path: Path) -> None:
    data = _minimal_config()
    data["entities"][0]["aliases"] = ["Alpha", "ＡＬＰＨＡ"]

    with pytest.raises(ConfigError, match="duplicate normalized label"):
        load_config(_write_config(tmp_path, data))


def test_allows_same_normalized_alias_across_entities(tmp_path: Path) -> None:
    data = _minimal_config()
    data["entities"].append({"id": "entity-2", "name": "Beta", "aliases": ["Alpha"]})

    loaded = load_config(_write_config(tmp_path, data))

    assert tuple(entity.id for entity in loaded.entities) == ("entity-1", "entity-2")


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data.update(unrecognized=True),
        lambda data: data["entities"][0].update(unrecognized=True),
        lambda data: data["matching"].update(unrecognized=True),
        lambda data: data["matching"]["candidate_rules"][0].update(unrecognized=True),
        lambda data: data["matching"].update(
            candidate_rules=[{"id": "unknown", "type": "fuzzy_name"}]
        ),
    ],
    ids=["top-level-key", "entity-key", "matching-key", "rule-key", "rule-type"],
)
def test_rejects_unknown_keys_and_rule_types(tmp_path: Path, change) -> None:
    data = _minimal_config()
    change(data)

    with pytest.raises(ConfigError):
        load_config(_write_config(tmp_path, data))


@pytest.mark.parametrize(
    "field",
    ["attributes.", "attributes.year.region", "attributes.\x00year", "id", "unknown"],
)
def test_rejects_invalid_field_references(tmp_path: Path, field: str) -> None:
    data = _minimal_config()
    data["matching"]["candidate_rules"] = [
        {
            "id": "exact",
            "type": "exact_value",
            "entity_field": field,
            "record_field": "attributes.external_id",
        }
    ]

    with pytest.raises(ConfigError, match="field reference"):
        load_config(_write_config(tmp_path, data))


@pytest.mark.parametrize("value", [{"nested": "value"}, ["nested"]])
def test_rejects_nested_attribute_values(tmp_path: Path, value: object) -> None:
    data = _minimal_config()
    data["entities"][0]["attributes"] = {"value": value}

    with pytest.raises(ConfigError, match="scalar"):
        load_config(_write_config(tmp_path, data))


def test_attribute_field_references_support_user_defined_unicode_keys(tmp_path: Path) -> None:
    data = _minimal_config()
    data["entities"][0]["attributes"] = {"出版者 名稱": "Fictional Press"}
    data["records"][0]["attributes"] = {"出版者 名稱": "Fictional Press"}
    data["matching"]["candidate_rules"] = [
        {
            "id": "publisher",
            "type": "exact_value",
            "entity_field": "attributes.出版者 名稱",
            "record_field": "attributes.出版者 名稱",
        }
    ]

    loaded = load_config(_write_config(tmp_path, data))

    assert loaded.config.candidate_rules[0].entity_field == "attributes.出版者 名稱"


def test_rejects_duplicate_yaml_mapping_keys(tmp_path: Path) -> None:
    path = tmp_path / "entitylinkage.yaml"
    path.write_text(
        "version: 1\nversion: 1\nentities: []\nrecords: []\nmatching: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="duplicate YAML key"):
        load_config(path)


def test_rejects_unquoted_yaml_date_attribute(tmp_path: Path) -> None:
    path = tmp_path / "entitylinkage.yaml"
    path.write_text(
        """version: 1
entities:
  - id: entity-1
    name: Alpha
    attributes:
      published: 2024-01-02
records: [{id: record-1}]
matching:
  normalization: {case_fold: true, punctuation: preserve}
  candidate_rules: [{id: name, type: normalized_name}]
  apply_overrides: false
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="scalar"):
        load_config(path)


def test_rejects_non_boolean_applicable_and_requires_reason_when_false(tmp_path: Path) -> None:
    data = _minimal_config()
    data["records"][0]["applicable"] = "false"
    with pytest.raises(ConfigError, match="applicable"):
        load_config(_write_config(tmp_path, data))

    data["records"][0]["applicable"] = False
    with pytest.raises(ConfigError, match="not_applicable_reason"):
        load_config(_write_config(tmp_path, data))


@pytest.mark.parametrize("number", [".nan", ".inf", "-.inf"])
def test_rejects_non_finite_float_attributes(tmp_path: Path, number: str) -> None:
    path = tmp_path / "entitylinkage.yaml"
    path.write_text(
        f"""version: 1
entities:
  - id: entity-1
    name: Alpha
    attributes: {{value: {number}}}
records: [{{id: record-1}}]
matching:
  normalization: {{case_fold: true, punctuation: preserve}}
  candidate_rules: [{{id: name, type: normalized_name}}]
  apply_overrides: false
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="finite"):
        load_config(path)


def test_directory_without_config_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="entitylinkage.yaml"):
        load_config(tmp_path)
