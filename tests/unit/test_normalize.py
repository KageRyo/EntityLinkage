import pytest

from entitylinkage.model import NormalizationConfig
from entitylinkage.normalize import normalize_text


def test_nfkc_punctuation_whitespace_and_casefold_are_applied_in_order() -> None:
    config = NormalizationConfig(case_fold=True, punctuation="space")

    assert normalize_text("  Ａlpha—B  ", config) == "alpha b"


def test_casefold_can_be_disabled() -> None:
    config = NormalizationConfig(case_fold=False, punctuation="preserve")

    assert normalize_text("  Alpha  ", config) == "Alpha"


@pytest.mark.parametrize(
    ("punctuation", "expected"),
    [("preserve", "a,b"), ("remove", "ab"), ("space", "a b")],
)
def test_unicode_punctuation_mode(punctuation: str, expected: str) -> None:
    config = NormalizationConfig(case_fold=True, punctuation=punctuation)  # type: ignore[arg-type]

    assert normalize_text("A,B", config) == expected


def test_unicode_whitespace_collapses_and_trims() -> None:
    config = NormalizationConfig(case_fold=True, punctuation="preserve")

    assert normalize_text(" A\u00a0 B\tC\n", config) == "a b c"
