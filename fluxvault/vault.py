"""FluxVault: ties the pieces together.

store():    seal data -> split DEK into n shares -> distribute (k-of-n).
flux():     proactively reshare the DEK across locations (cheap, frequent).
rotate():   re-key the bulk data under a fresh DEK and reshare (heavier).
retrieve(): require a valid lease -> gather k shares -> reconstruct -> decrypt.

Every state-changing operation is recorded in a tamper-evident audit log.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import aead, shamir
from .audit import AuditLog
from .leases import Lease, LeaseAuthority
from .store import LocationStore


class VaultError(Exception):
    pass


@dataclass
class FluxVault:
    vault_id: str
    n: int
    k: int
    store: LocationStore
    authority: LeaseAuthority
    audit: AuditLog

    def __post_init__(self) -> None:
        if not 2 <= self.k <= self.n:
            raise VaultError("require 2 <= k <= n")
        if len(self.store.location_ids) != self.n:
            raise VaultError("store must have exactly n locations")

    # --- lifecycle ---------------------------------------------------------
    def store_data(self, plaintext: bytes) -> None:
        dek = aead.new_dek()
        aad = self.vault_id.encode("utf-8")
        blob = aead.seal(dek, plaintext, aad)
        shares = shamir.split(dek, self.n, self.k)
        self.store.put_ciphertext(blob)
        self.store.put_shares(shares)
        self.audit.append("store", {"vault": self.vault_id, "bytes": len(plaintext)})

    def flux(self) -> None:
        """One epoch of 'constant flux': reshare the DEK, leave ciphertext be."""
        shares = self.store.online_shares()
        if len(shares) < self.k:
            raise VaultError("not enough online shares to reshare safely")
        # Reshare across ALL locations using their stored x-coordinates so the
        # secret is preserved everywhere, not just the online subset.
        all_shares = [
            self.store._locs[lid].share for lid in self.store.location_ids
        ]
        if any(s is None for s in all_shares):
            raise VaultError("cannot flux before data is stored")
        new_shares = shamir.reshare(all_shares, self.k)
        self.store.put_shares(new_shares)
        self.audit.append("flux", {"vault": self.vault_id})

    def rotate(self) -> None:
        """Full key rotation: decrypt with old DEK, re-encrypt under a new one,
        reshare. Heavier than flux(); run it on a slower cadence."""
        dek_old = shamir.combine(self.store.online_shares()[: self.k])
        aad = self.vault_id.encode("utf-8")
        plaintext = aead.open_sealed(dek_old, self.store.any_ciphertext(), aad)
        dek_new = aead.new_dek()
        blob = aead.seal(dek_new, plaintext, aad)
        shares = shamir.split(dek_new, self.n, self.k)
        self.store.put_ciphertext(blob)
        self.store.put_shares(shares)
        self.audit.append("rotate", {"vault": self.vault_id})

    # --- access ------------------------------------------------------------
    def retrieve(self, subject: str, lease: Lease) -> bytes:
        # The time window: a valid, unexpired lease is mandatory.
        self.authority.verify(lease, subject, self.vault_id)

        shares = self.store.online_shares()
        if len(shares) < self.k:
            self.audit.append(
                "retrieve_denied",
                {"vault": self.vault_id, "subject": subject, "reason": "quorum"},
            )
            raise VaultError(
                f"only {len(shares)} shares online; need {self.k}"
            )
        dek = shamir.combine(shares[: self.k])
        aad = self.vault_id.encode("utf-8")
        plaintext = aead.open_sealed(dek, self.store.any_ciphertext(), aad)
        self.audit.append(
            "retrieve", {"vault": self.vault_id, "subject": subject}
        )
        return plaintext
