import unicodedata

from entitylinkage.model import NormalizationConfig


def normalize_text(value: str, config: NormalizationConfig) -> str:
    """Apply the configured deterministic normalization to a name or alias."""
    normalized = unicodedata.normalize("NFKC", value)

    if config.punctuation != "preserve":
        replacement = " " if config.punctuation == "space" else ""
        normalized = "".join(
            replacement if unicodedata.category(character).startswith("P") else character
            for character in normalized
        )

    if config.case_fold:
        normalized = normalized.casefold()

    return " ".join(normalized.split())
