from __future__ import annotations

from typing import Protocol


class CredentialProtector(Protocol):
    """Future encryption boundary for target credentials."""

    def protect(self, value: str | None) -> str | None:
        """Protect a credential payload before persistence."""


class MaskingCredentialProtector:
    """Prototype-safe protector that stores no credential secret."""

    def protect(self, value: str | None) -> str | None:
        """Store a marker until a project encryption provider is available."""
        if value is None or not value.strip():
            return None
        # TODO: replace with an injected KMS/secret-manager implementation.
        return "[configured credentials]"


credential_protector: CredentialProtector = MaskingCredentialProtector()
