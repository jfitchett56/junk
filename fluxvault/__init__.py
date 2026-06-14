"""FluxVault — a proof-of-concept for *safe* moving-target data protection.

This package demonstrates the defensible building blocks behind the
"data in constant flux" idea, without the self-destruct/tamper-kill
storage substrate that makes the naive version dangerous:

    * Shamir threshold secret sharing      (lose a location, still recover)
    * Proactive re-sharing ("flux")        (shares churn; secret unchanged)
    * Envelope encryption with AES-256-GCM (the data key is what's shared)
    * Short-lived access leases            (time-windowed, credential-gated)
    * Hash-chained tamper-EVIDENT audit    (detect interference, don't destroy)

See README.md for how each piece maps to the original idea and where the
honest limitations are.
"""

from .shamir import Share, split, combine, reshare
from .aead import seal, open_sealed
from .leases import LeaseAuthority, Lease, LeaseError
from .audit import AuditLog, AuditError
from .store import LocationStore, StoreError
from .vault import FluxVault, VaultError

__all__ = [
    "Share",
    "split",
    "combine",
    "reshare",
    "seal",
    "open_sealed",
    "LeaseAuthority",
    "Lease",
    "LeaseError",
    "AuditLog",
    "AuditError",
    "LocationStore",
    "StoreError",
    "FluxVault",
    "VaultError",
]
