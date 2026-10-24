from dataclasses import FrozenInstanceError

import pytest

from entitylinkage.model import (
    Entity,
    Evidence,
)


def test_models_are_frozen_and_copy_attribute_mappings() -> None:
    attributes = {"year": 2024}
    entity = Entity(id="entity-1", name="Example", attributes=attributes)
    details = {"record_value": "Example"}
    evidence = Evidence(
        rule_id="name",
        phase="candidate",
        outcome="match",
        entity_id="entity-1",
        details=details,
    )

    attributes["year"] = 2025
    details["record_value"] = "Changed"

    assert entity.attributes["year"] == 2024
    assert evidence.details["record_value"] == "Example"
    with pytest.raises(TypeError):
        entity.attributes["year"] = 2026
    with pytest.raises(TypeError):
        evidence.details["record_value"] = "Changed again"
    with pytest.raises(FrozenInstanceError):
        entity.name = "Changed"
