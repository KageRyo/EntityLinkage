from entitylinkage.audit import audit_results
from entitylinkage.model import LinkageResult


def _result(record_id: str, status: str, reason_codes: tuple[str, ...] = ()) -> LinkageResult:
    entity_id = "entity-1" if status == "resolved" else None
    candidates = (entity_id,) if entity_id is not None else ()
    return LinkageResult(
        record_id=record_id,
        status=status,
        entity_id=entity_id,
        candidate_entity_ids=candidates,
        reason_codes=reason_codes,
        normalized_record_name=None,
        evidence=(),
    )


def test_audit_counts_all_statuses_and_sorts_reason_counts() -> None:
    results = (
        _result("r4", "not_applicable", ("outside_scope",)),
        _result("r3", "unresolved", ("no_identity_candidate", "manual_review")),
        _result("r2", "ambiguous", ("multiple_valid_candidates",)),
        _result("r1", "resolved", ()),
        _result("r5", "unresolved", ("manual_review",)),
    )

    summary = audit_results(results)

    assert dict(summary.status_counts) == {
        "ambiguous": 1,
        "not_applicable": 1,
        "resolved": 1,
        "unresolved": 2,
    }
    assert dict(summary.reason_code_counts) == {
        "manual_review": 2,
        "multiple_valid_candidates": 1,
        "no_identity_candidate": 1,
        "outside_scope": 1,
    }
