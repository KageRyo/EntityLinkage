from collections.abc import Sequence

from entitylinkage.errors import ConfigError
from entitylinkage.model import (
    Entity,
    Evidence,
    LinkageConfig,
    LinkageResult,
    Record,
    Scalar,
)
from entitylinkage.normalize import normalize_text
from entitylinkage.overrides import apply_override


class Linker:
    """Apply configured exact rules without scoring or guessing between candidates."""

    def __init__(self, config: LinkageConfig) -> None:
        self.config = config

    def link(
        self, entities: Sequence[Entity], records: Sequence[Record]
    ) -> tuple[LinkageResult, ...]:
        ordered_entities = tuple(sorted(entities, key=lambda item: item.id))
        results = (self._link_record(ordered_entities, record) for record in records)
        return tuple(sorted(results, key=lambda item: item.record_id))

    def _link_record(self, entities: tuple[Entity, ...], record: Record) -> LinkageResult:
        if not record.applicable:
            reason_codes = (record.not_applicable_reason,) if record.not_applicable_reason else ()
            return LinkageResult(
                record_id=record.id,
                status="not_applicable",
                entity_id=None,
                candidate_entity_ids=(),
                reason_codes=reason_codes,
                normalized_record_name=None,
                evidence=(),
            )

        if self.config.apply_overrides:
            override_result = apply_override(
                record,
                {entity.id: entity for entity in entities},
                {override.record_id: override for override in self.config.overrides},
            )
            if override_result is not None:
                return override_result

        normalized_record_name = (
            normalize_text(record.name, self.config.normalization)
            if record.name is not None
            else None
        )
        generated: set[str] = set()
        evidence: list[Evidence] = []
        usable_identity_input = False

        for rule in sorted(self.config.candidate_rules, key=lambda item: item.id):
            if rule.type == "normalized_name":
                name_is_usable = bool(normalized_record_name)
                usable_identity_input |= name_is_usable
                for entity in entities:
                    labels = self._normalized_labels(entity)
                    match = next(
                        (
                            (kind, label)
                            for kind, label in labels
                            if name_is_usable and label == normalized_record_name
                        ),
                        None,
                    )
                    if match is not None:
                        generated.add(entity.id)
                        outcome = "match"
                        details: dict[str, Scalar | tuple[Scalar, ...]] = {
                            "record_value": normalized_record_name,
                            "matched_label": match[0],
                            "matched_value": match[1],
                        }
                    else:
                        outcome = "no_match" if name_is_usable else "missing_input"
                        details = {
                            "record_value": normalized_record_name,
                            "entity_values": tuple(label for _, label in labels),
                        }
                    evidence.append(
                        Evidence(
                            rule_id=rule.id,
                            phase="candidate",
                            outcome=outcome,
                            entity_id=entity.id,
                            details=details,
                        )
                    )
                continue

            if rule.type != "exact_value":
                raise ConfigError(f"unsupported candidate rule type: {rule.type}")
            if rule.entity_field is None or rule.record_field is None:
                raise ConfigError(f"exact_value rule {rule.id!r} requires both field references")

            record_value = _field_value(record, rule.record_field)
            value_is_usable = record_value is not None and record_value != ""
            usable_identity_input |= value_is_usable
            for entity in entities:
                entity_value = _field_value(entity, rule.entity_field)
                values_are_usable = entity_value is not None and entity_value != ""
                is_match = (
                    value_is_usable
                    and values_are_usable
                    and _type_sensitive_equal(record_value, entity_value)
                )
                if is_match:
                    generated.add(entity.id)
                    outcome = "match"
                elif not value_is_usable:
                    outcome = "missing_input"
                elif not values_are_usable:
                    outcome = "missing_entity_value"
                else:
                    outcome = "no_match"
                evidence.append(
                    Evidence(
                        rule_id=rule.id,
                        phase="candidate",
                        outcome=outcome,
                        entity_id=entity.id,
                        details={
                            "record_field": rule.record_field,
                            "record_value": record_value,
                            "entity_field": rule.entity_field,
                            "entity_value": entity_value,
                        },
                    )
                )

        if not generated:
            reason = "no_identity_candidate" if usable_identity_input else "insufficient_metadata"
            return LinkageResult(
                record_id=record.id,
                status="unresolved",
                entity_id=None,
                candidate_entity_ids=(),
                reason_codes=(reason,),
                normalized_record_name=normalized_record_name,
                evidence=tuple(evidence),
            )

        surviving: list[str] = []
        reason_codes: set[str] = set()
        for entity_id in sorted(generated):
            entity = next(item for item in entities if item.id == entity_id)
            candidate_passes = True
            for constraint in sorted(self.config.constraints, key=lambda item: item.id):
                entity_value = _field_value(entity, constraint.entity_field)
                record_value = _field_value(record, constraint.record_field)
                if entity_value is None or record_value is None:
                    outcome = (
                        "missing_ignored" if constraint.missing == "ignore" else "missing_rejected"
                    )
                    if constraint.missing == "reject":
                        candidate_passes = False
                        reason_codes.add("insufficient_metadata")
                elif _type_sensitive_equal(entity_value, record_value):
                    outcome = "match"
                else:
                    outcome = "mismatch"
                    candidate_passes = False
                    reason_codes.add("attribute_conflict")
                evidence.append(
                    Evidence(
                        rule_id=constraint.id,
                        phase="constraint",
                        outcome=outcome,
                        entity_id=entity_id,
                        details={
                            "entity_field": constraint.entity_field,
                            "entity_value": entity_value,
                            "record_field": constraint.record_field,
                            "record_value": record_value,
                        },
                    )
                )
            if candidate_passes:
                surviving.append(entity_id)

        if not surviving:
            return LinkageResult(
                record_id=record.id,
                status="unresolved",
                entity_id=None,
                candidate_entity_ids=(),
                reason_codes=tuple(reason_codes),
                normalized_record_name=normalized_record_name,
                evidence=tuple(evidence),
            )

        if len(surviving) == 1:
            status = "resolved"
            entity_id = surviving[0]
        else:
            status = "ambiguous"
            entity_id = None
            reason_codes.add("multiple_valid_candidates")

        return LinkageResult(
            record_id=record.id,
            status=status,
            entity_id=entity_id,
            candidate_entity_ids=tuple(surviving),
            reason_codes=tuple(reason_codes),
            normalized_record_name=normalized_record_name,
            evidence=tuple(evidence),
        )

    def _normalized_labels(self, entity: Entity) -> tuple[tuple[str, str], ...]:
        labels: list[tuple[str, str]] = []
        normalized_name = normalize_text(entity.name, self.config.normalization)
        if normalized_name:
            labels.append(("name", normalized_name))
        for alias in sorted(set(entity.aliases)):
            normalized_alias = normalize_text(alias, self.config.normalization)
            if normalized_alias:
                labels.append(("alias", normalized_alias))
        return tuple(labels)


def _field_value(entity_or_record: Entity | Record, reference: str) -> Scalar:
    if reference == "name":
        return entity_or_record.name
    if reference.startswith("attributes.") and reference.removeprefix("attributes."):
        return entity_or_record.attributes.get(reference.removeprefix("attributes."))
    raise ConfigError(f"invalid field reference: {reference!r}")


def _type_sensitive_equal(left: Scalar, right: Scalar) -> bool:
    return type(left) is type(right) and left == right
