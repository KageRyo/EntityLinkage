class EntityLinkageError(Exception):
    """Base exception for expected EntityLinkage failures."""


class ConfigError(EntityLinkageError):
    """Raised when a linkage configuration is invalid."""
