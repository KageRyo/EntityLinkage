from collections import Counter
from collections.abc import Sequence

from entitylinkage.model import AuditSummary, LinkageResult, LinkageStatus

_STATUSES: tuple[LinkageStatus, ...] = (
    "ambiguous",
    "not_applicable",
    "resolved",
    "unresolved",
)


def audit_results(results: Sequence[LinkageResult]) -> AuditSummary:
    """Count statuses and the records carrying each stable reason code."""
    status_counts = dict.fromkeys(_STATUSES, 0)
    reason_code_counts: Counter[str] = Counter()
    for result in results:
        if result.status not in status_counts:
            raise ValueError(f"unsupported linkage status: {result.status!r}")
        status_counts[result.status] += 1
        reason_code_counts.update(set(result.reason_codes))
    return AuditSummary(
        status_counts=status_counts,
        reason_code_counts=dict(reason_code_counts),
    )
