"""Multi-location storage simulation.

Each location holds a *replica* of the sealed ciphertext (for availability)
plus *one* secret share of the data key (for threshold security). Losing up
to (n - k) locations loses no data: the ciphertext is still available from a
surviving replica, and k shares still reconstruct the key.

This is an in-memory simulation; a real deployment would put each location in
a separate failure/trust domain (region, provider, custodian).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .shamir import Share


class StoreError(Exception):
    pass


@dataclass
class _Location:
    location_id: str
    online: bool = True
    ciphertext: Optional[bytes] = None
    share: Optional[Share] = None


@dataclass
class LocationStore:
    location_ids: List[str]
    _locs: Dict[str, _Location] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(set(self.location_ids)) != len(self.location_ids):
            raise StoreError("duplicate location ids")
        self._locs = {lid: _Location(lid) for lid in self.location_ids}

    # --- write paths -------------------------------------------------------
    def put_ciphertext(self, blob: bytes) -> None:
        for loc in self._locs.values():
            loc.ciphertext = blob  # replicated to every location

    def put_shares(self, shares: List[Share]) -> None:
        ids = list(self._locs)
        if len(shares) != len(ids):
            raise StoreError("expected one share per location")
        for lid, share in zip(ids, shares):
            self._locs[lid].share = share

    # --- fault injection (for the demo/tests) ------------------------------
    def set_online(self, location_id: str, online: bool) -> None:
        if location_id not in self._locs:
            raise StoreError(f"unknown location {location_id}")
        self._locs[location_id].online = online

    # --- read paths --------------------------------------------------------
    def online_shares(self) -> List[Share]:
        return [
            loc.share
            for loc in self._locs.values()
            if loc.online and loc.share is not None
        ]

    def any_ciphertext(self) -> bytes:
        for loc in self._locs.values():
            if loc.online and loc.ciphertext is not None:
                return loc.ciphertext
        raise StoreError("no online location holds the ciphertext")

    def online_count(self) -> int:
        return sum(1 for loc in self._locs.values() if loc.online)
