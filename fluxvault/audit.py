"""Hash-chained, tamper-EVIDENT audit log.

This is the deliberate replacement for "any attempt to stop it destroys the
data". Instead of self-destructing on interference (which makes power blips,
bugs and network partitions indistinguishable from attacks and guarantees
data loss), we make interference *detectable*: each entry commits to the hash
of the previous one, so any insertion, deletion or edit anywhere in the chain
is provable after the fact. Detection drives alerting and key rotation, not
destruction.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from hashlib import sha256
from typing import List

_GENESIS = "0" * 64


class AuditError(Exception):
    pass


@dataclass(frozen=True)
class AuditEntry:
    index: int
    timestamp: float
    event: str
    detail: dict
    prev_hash: str
    this_hash: str


def _hash_entry(index, timestamp, event, detail, prev_hash) -> str:
    payload = json.dumps(
        {
            "index": index,
            "timestamp": timestamp,
            "event": event,
            "detail": detail,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass
class AuditLog:
    _entries: List[AuditEntry] = field(default_factory=list)

    def append(self, event: str, detail: dict | None = None, *, clock=time.time) -> AuditEntry:
        detail = detail or {}
        index = len(self._entries)
        prev_hash = self._entries[-1].this_hash if self._entries else _GENESIS
        ts = clock()
        this_hash = _hash_entry(index, ts, event, detail, prev_hash)
        entry = AuditEntry(index, ts, event, detail, prev_hash, this_hash)
        self._entries.append(entry)
        return entry

    def verify(self) -> None:
        """Raise AuditError at the first sign of tampering."""
        prev_hash = _GENESIS
        for i, e in enumerate(self._entries):
            if e.index != i:
                raise AuditError(f"entry {i} has wrong index {e.index}")
            if e.prev_hash != prev_hash:
                raise AuditError(f"entry {i} breaks the hash chain")
            recomputed = _hash_entry(e.index, e.timestamp, e.event, e.detail, e.prev_hash)
            if recomputed != e.this_hash:
                raise AuditError(f"entry {i} content was modified")
            prev_hash = e.this_hash

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> List[AuditEntry]:
        return list(self._entries)
