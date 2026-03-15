class ProtocolError(ValueError):
    """Base protocol error for validation/signature failures."""


class SignatureError(ProtocolError):
    """Raised when signature verification fails."""


class TokenValidationError(ProtocolError):
    """Raised when a token does not match protocol constraints."""


class ResourceLimitError(ProtocolError):
    """Raised when an in-memory security store reaches its capacity."""
