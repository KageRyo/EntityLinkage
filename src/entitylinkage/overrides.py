from collections.abc import Mapping

from entitylinkage.errors import ConfigError
from entitylinkage.model import Entity, Evidence, LinkageResult, Override, Record


def apply_override(
    record: Record,
    entities_by_id: Mapping[str, Entity],
    overrides_by_record_id: Mapping[str, Override],
) -> LinkageResult | None:
    """Return the explicit reviewed decision for a record, if one is configured."""
    override = overrides_by_record_id.get(record.id)
    if override is None:
        return None
    if not record.applicable:
        raise ConfigError(f"override for record {record.id!r} contradicts not_applicable input")
    if override.entity_id is not None and override.entity_id not in entities_by_id:
        raise ConfigError(f"override refers to unknown entity {override.entity_id!r}")
    if override.status == "resolved":
        if override.entity_id is None:
            raise ConfigError(f"resolved override for record {record.id!r} requires entity_id")
        entity_id = override.entity_id
        candidate_entity_ids = (entity_id,)
    elif override.status == "not_applicable":
        if override.entity_id is not None:
            raise ConfigError(
                f"not_applicable override for record {record.id!r} must omit entity_id"
            )
        entity_id = None
        candidate_entity_ids = ()
    else:
        raise ConfigError(f"unsupported override status: {override.status!r}")
    return LinkageResult(
        record_id=record.id,
        status=override.status,
        entity_id=entity_id,
        candidate_entity_ids=candidate_entity_ids,
        reason_codes=(override.reason,),
        normalized_record_name=None,
        evidence=(
            Evidence(
                rule_id="manual_override",
                phase="override",
                outcome=override.status,
                entity_id=entity_id,
                details={"reason": override.reason},
            ),
        ),
    )
