"""Short-lived, credential-gated access leases.

A lease is the "time window" from the original idea: retrieval is only
permitted while a valid, unexpired lease exists. Leases are HMAC-signed by
an authority so they cannot be forged, and they carry an explicit expiry so
access is inherently temporary.
"""

from __future__ import annotations

import hmac
import os
import time
from dataclasses import dataclass
from hashlib import sha256


class LeaseError(Exception):
    pass


@dataclass(frozen=True)
class Lease:
    subject: str       # who the lease is for
    vault_id: str      # which vault it grants access to
    issued_at: float
    expires_at: float
    nonce: str
    mac: str

    def _signing_bytes(self) -> bytes:
        return "|".join(
            [
                self.subject,
                self.vault_id,
                repr(self.issued_at),
                repr(self.expires_at),
                self.nonce,
            ]
        ).encode("utf-8")


class LeaseAuthority:
    """Issues and verifies leases. Holds the signing secret."""

    def __init__(self, secret: bytes | None = None, *, clock=time.time):
        self._secret = secret or os.urandom(32)
        self._clock = clock

    def issue(self, subject: str, vault_id: str, ttl_seconds: float) -> Lease:
        if ttl_seconds <= 0:
            raise LeaseError("ttl must be positive")
        now = self._clock()
        nonce = os.urandom(16).hex()
        partial = Lease(subject, vault_id, now, now + ttl_seconds, nonce, mac="")
        mac = hmac.new(self._secret, partial._signing_bytes(), sha256).hexdigest()
        return Lease(subject, vault_id, now, now + ttl_seconds, nonce, mac)

    def verify(self, lease: Lease, subject: str, vault_id: str) -> None:
        """Raise LeaseError unless the lease is authentic, unexpired and
        matches the requested subject + vault."""
        expected = hmac.new(
            self._secret, lease._signing_bytes(), sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, lease.mac):
            raise LeaseError("lease signature invalid (forged or tampered)")
        if lease.subject != subject:
            raise LeaseError("lease subject mismatch")
        if lease.vault_id != vault_id:
            raise LeaseError("lease vault mismatch")
        now = self._clock()
        if now < lease.issued_at:
            raise LeaseError("lease not yet valid")
        if now >= lease.expires_at:
            raise LeaseError("lease expired")
