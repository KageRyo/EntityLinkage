from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver

from entitylinkage.errors import ConfigError
from entitylinkage.model import (
    CandidateRule,
    Entity,
    EqualConstraint,
    LinkageConfig,
    LinkageInput,
    NormalizationConfig,
    Override,
    Record,
    Scalar,
)
from entitylinkage.normalize import normalize_text

_ATTRIBUTE_KEY = re.compile(r"[^.\x00-\x1f\x7f]+\Z")
_REASON_CODE = re.compile(r"[a-z][a-z0-9_]*\Z")


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate YAML key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def load_config(path: Path) -> LinkageInput:
    """Read and strictly validate an EntityLinkage YAML file or example directory."""
    source = path / "entitylinkage.yaml" if path.is_dir() else path
    try:
        with source.open(encoding="utf-8") as stream:
            document = yaml.load(stream, Loader=_UniqueKeySafeLoader)
    except OSError as error:
        raise ConfigError(
            f"cannot read configuration {source}: {error.strerror or error}"
        ) from error
    except yaml.YAMLError as error:
        message = str(error)
        if "duplicate YAML key" in message:
            raise ConfigError(message) from error
        raise ConfigError(f"invalid YAML: {message}") from error

    root = _mapping(
        document,
        "configuration",
        allowed={"version", "entities", "records", "matching", "overrides"},
        required={"version", "entities", "records", "matching"},
    )
    version = root["version"]
    if type(version) is not int or version != 1:
        raise ConfigError("version must be the integer 1")

    entities = tuple(
        _parse_entity(item, index) for index, item in enumerate(_list(root["entities"], "entities"))
    )
    records = tuple(
        _parse_record(item, index) for index, item in enumerate(_list(root["records"], "records"))
    )
    _require_unique((entity.id for entity in entities), "entity ID")
    _require_unique((record.id for record in records), "record ID")

    matching = _mapping(
        root["matching"],
        "matching",
        allowed={"normalization", "candidate_rules", "constraints", "apply_overrides"},
        required={"normalization", "candidate_rules", "apply_overrides"},
    )
    normalization = _parse_normalization(matching["normalization"])
    candidate_rules = tuple(
        _parse_candidate_rule(item, index)
        for index, item in enumerate(_list(matching["candidate_rules"], "matching.candidate_rules"))
    )
    if not candidate_rules:
        raise ConfigError("matching.candidate_rules must not be empty")
    constraints = tuple(
        _parse_constraint(item, index)
        for index, item in enumerate(_list(matching.get("constraints", []), "matching.constraints"))
    )
    rule_ids = [rule.id for rule in candidate_rules] + [constraint.id for constraint in constraints]
    _require_unique(rule_ids, "rule ID")

    apply_overrides = matching["apply_overrides"]
    if type(apply_overrides) is not bool:
        raise ConfigError("matching.apply_overrides must be a boolean")

    overrides = tuple(
        _parse_override(item, index)
        for index, item in enumerate(_list(root.get("overrides", []), "overrides"))
    )
    _require_unique((override.record_id for override in overrides), "override record ID")
    if overrides and not apply_overrides:
        raise ConfigError("overrides require matching.apply_overrides: true")

    _validate_entity_labels(entities, normalization)
    _validate_references(candidate_rules, constraints)
    _validate_overrides(entities, records, overrides)

    return LinkageInput(
        entities=entities,
        records=records,
        config=LinkageConfig(
            normalization=normalization,
            candidate_rules=candidate_rules,
            apply_overrides=apply_overrides,
            constraints=constraints,
            overrides=overrides,
        ),
    )


def _mapping(
    value: object,
    context: str,
    *,
    allowed: set[str],
    required: set[str] = frozenset(),
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigError(f"{context} must be a mapping")
    if any(type(key) is not str for key in value):
        raise ConfigError(f"{context} keys must be strings")
    keys = set(value)
    unknown = sorted(keys - allowed)
    missing = sorted(required - keys)
    if unknown:
        raise ConfigError(f"{context} contains unknown keys: {', '.join(unknown)}")
    if missing:
        raise ConfigError(f"{context} is missing required keys: {', '.join(missing)}")
    return value


def _list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ConfigError(f"{context} must be a list")
    return value


def _string(value: object, context: str, *, nonempty: bool = False) -> str:
    if type(value) is not str or (nonempty and not value.strip()):
        suffix = " nonempty" if nonempty else ""
        raise ConfigError(f"{context} must be a{suffix} string")
    return value


def _boolean(value: object, context: str) -> bool:
    if type(value) is not bool:
        raise ConfigError(f"{context} must be a boolean")
    return value


def _scalar(value: object, context: str) -> Scalar:
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ConfigError(f"{context} must be a finite scalar")
        return value
    raise ConfigError(f"{context} must be a flat scalar (string, integer, float, boolean, or null)")


def _attributes(value: object, context: str) -> dict[str, Scalar]:
    if not isinstance(value, dict):
        raise ConfigError(f"{context} must be a flat mapping")
    attributes: dict[str, Scalar] = {}
    for key, item in value.items():
        attribute_key = _string(key, f"{context} key", nonempty=True)
        if _ATTRIBUTE_KEY.fullmatch(attribute_key) is None:
            raise ConfigError(f"{context} key {attribute_key!r} must be one flat field name")
        attributes[attribute_key] = _scalar(item, f"{context}.{attribute_key}")
    return attributes


def _parse_entity(value: object, index: int) -> Entity:
    context = f"entities[{index}]"
    item = _mapping(
        value,
        context,
        allowed={"id", "name", "aliases", "attributes"},
        required={"id", "name"},
    )
    aliases = tuple(
        _string(alias, f"{context}.aliases[{alias_index}]", nonempty=True)
        for alias_index, alias in enumerate(_list(item.get("aliases", []), f"{context}.aliases"))
    )
    return Entity(
        id=_string(item["id"], f"{context}.id", nonempty=True),
        name=_string(item["name"], f"{context}.name", nonempty=True),
        aliases=aliases,
        attributes=_attributes(item.get("attributes", {}), f"{context}.attributes"),
    )


def _parse_record(value: object, index: int) -> Record:
    context = f"records[{index}]"
    item = _mapping(
        value,
        context,
        allowed={"id", "name", "attributes", "applicable", "not_applicable_reason"},
        required={"id"},
    )
    name = item.get("name")
    if name is not None:
        name = _string(name, f"{context}.name")
    applicable = _boolean(item.get("applicable", True), f"{context}.applicable")
    not_applicable_reason = item.get("not_applicable_reason")
    if not_applicable_reason is not None:
        not_applicable_reason = _reason_code(
            not_applicable_reason, f"{context}.not_applicable_reason"
        )
    if not applicable and not_applicable_reason is None:
        raise ConfigError(f"{context} with applicable: false requires not_applicable_reason")
    return Record(
        id=_string(item["id"], f"{context}.id", nonempty=True),
        name=name,
        attributes=_attributes(item.get("attributes", {}), f"{context}.attributes"),
        applicable=applicable,
        not_applicable_reason=not_applicable_reason,
    )


def _parse_normalization(value: object) -> NormalizationConfig:
    item = _mapping(
        value,
        "matching.normalization",
        allowed={"case_fold", "punctuation"},
        required={"case_fold", "punctuation"},
    )
    case_fold = _boolean(item["case_fold"], "matching.normalization.case_fold")
    punctuation = _string(item["punctuation"], "matching.normalization.punctuation")
    if punctuation not in {"preserve", "remove", "space"}:
        raise ConfigError("matching.normalization.punctuation must be preserve, remove, or space")
    return NormalizationConfig(case_fold=case_fold, punctuation=punctuation)  # type: ignore[arg-type]


def _parse_candidate_rule(value: object, index: int) -> CandidateRule:
    context = f"matching.candidate_rules[{index}]"
    item = _mapping(
        value,
        context,
        allowed={"id", "type", "entity_field", "record_field"},
        required={"id", "type"},
    )
    rule_id = _string(item["id"], f"{context}.id", nonempty=True)
    rule_type = _string(item["type"], f"{context}.type")
    if rule_type == "normalized_name":
        if "entity_field" in item or "record_field" in item:
            raise ConfigError(f"{context} normalized_name rule does not accept field references")
        return CandidateRule(id=rule_id, type="normalized_name")
    if rule_type == "exact_value":
        if "entity_field" not in item or "record_field" not in item:
            raise ConfigError(f"{context} exact_value rule requires entity_field and record_field")
        return CandidateRule(
            id=rule_id,
            type="exact_value",
            entity_field=_field_reference(item["entity_field"], f"{context}.entity_field"),
            record_field=_field_reference(item["record_field"], f"{context}.record_field"),
        )
    raise ConfigError(f"{context} has unsupported rule type {rule_type!r}")


def _parse_constraint(value: object, index: int) -> EqualConstraint:
    context = f"matching.constraints[{index}]"
    item = _mapping(
        value,
        context,
        allowed={"id", "type", "entity_field", "record_field", "missing"},
        required={"id", "type", "entity_field", "record_field", "missing"},
    )
    constraint_type = _string(item["type"], f"{context}.type")
    if constraint_type != "equal":
        raise ConfigError(f"{context} has unsupported constraint type {constraint_type!r}")
    missing = _string(item["missing"], f"{context}.missing")
    if missing not in {"ignore", "reject"}:
        raise ConfigError(f"{context}.missing must be ignore or reject")
    return EqualConstraint(
        id=_string(item["id"], f"{context}.id", nonempty=True),
        entity_field=_field_reference(item["entity_field"], f"{context}.entity_field"),
        record_field=_field_reference(item["record_field"], f"{context}.record_field"),
        missing=missing,  # type: ignore[arg-type]
    )


def _field_reference(value: object, context: str) -> str:
    reference = _string(value, context, nonempty=True)
    if reference == "name":
        return reference
    if reference.startswith("attributes."):
        key = reference.removeprefix("attributes.")
        if _ATTRIBUTE_KEY.fullmatch(key):
            return reference
    raise ConfigError(f"{context} is an invalid field reference: {reference!r}")


def _reason_code(value: object, context: str) -> str:
    reason = _string(value, context)
    if _REASON_CODE.fullmatch(reason) is None:
        raise ConfigError(f"{context} must be a reason code matching [a-z][a-z0-9_]*")
    return reason


def _parse_override(value: object, index: int) -> Override:
    context = f"overrides[{index}]"
    item = _mapping(
        value,
        context,
        allowed={"record_id", "status", "entity_id", "reason"},
        required={"record_id", "status", "reason"},
    )
    status = _string(item["status"], f"{context}.status")
    if status == "resolved":
        if "entity_id" not in item:
            raise ConfigError(f"{context} resolved override requires entity_id")
        entity_id = _string(item["entity_id"], f"{context}.entity_id", nonempty=True)
    elif status == "not_applicable":
        if "entity_id" in item:
            raise ConfigError(f"{context} not_applicable override must omit entity_id")
        entity_id = None
    else:
        raise ConfigError(f"{context} has unsupported override status {status!r}")
    return Override(
        record_id=_string(item["record_id"], f"{context}.record_id", nonempty=True),
        status=status,  # type: ignore[arg-type]
        reason=_reason_code(item["reason"], f"{context}.reason"),
        entity_id=entity_id,
    )


def _require_unique(values, context: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ConfigError(f"duplicate {context}: {value!r}")
        seen.add(value)


def _validate_entity_labels(
    entities: tuple[Entity, ...], normalization: NormalizationConfig
) -> None:
    for entity in entities:
        labels = [entity.name, *entity.aliases]
        normalized = [normalize_text(label, normalization) for label in labels]
        if len(normalized) != len(set(normalized)):
            raise ConfigError(f"entity {entity.id!r} has a duplicate normalized label")


def _validate_references(
    candidate_rules: tuple[CandidateRule, ...], constraints: tuple[EqualConstraint, ...]
) -> None:
    for rule in candidate_rules:
        if rule.type == "exact_value":
            assert rule.entity_field is not None and rule.record_field is not None
            _field_reference(rule.entity_field, f"candidate rule {rule.id!r}.entity_field")
            _field_reference(rule.record_field, f"candidate rule {rule.id!r}.record_field")
    for constraint in constraints:
        _field_reference(constraint.entity_field, f"constraint {constraint.id!r}.entity_field")
        _field_reference(constraint.record_field, f"constraint {constraint.id!r}.record_field")


def _validate_overrides(
    entities: tuple[Entity, ...], records: tuple[Record, ...], overrides: tuple[Override, ...]
) -> None:
    entities_by_id = {entity.id: entity for entity in entities}
    records_by_id = {record.id: record for record in records}
    for override in overrides:
        if override.record_id not in records_by_id:
            raise ConfigError(f"override refers to unknown record {override.record_id!r}")
        record = records_by_id[override.record_id]
        if not record.applicable:
            raise ConfigError(
                f"override for record {override.record_id!r} contradicts "
                "an explicitly not applicable record"
            )
        if override.entity_id is not None and override.entity_id not in entities_by_id:
            raise ConfigError(f"override refers to unknown entity {override.entity_id!r}")
