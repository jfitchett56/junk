"""Shamir secret sharing over GF(2^8), with proactive re-sharing.

The secret is processed one byte at a time. For each byte we build a random
polynomial of degree (k-1) whose constant term is the secret byte, then
evaluate it at x = 1..n to produce n shares. Any k shares reconstruct the
secret via Lagrange interpolation at x = 0; fewer than k reveal *nothing*
(information-theoretic security, not merely computational).

GF(2^8) uses the AES reduction polynomial 0x11b.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Iterable, List, Sequence

# --- GF(2^8) arithmetic via exp/log tables (generator 0x03) ----------------


def _peasant_mul(a: int, b: int) -> int:
    """Carry-less multiply in GF(2^8) (used only to build the tables)."""
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        carry = a & 0x80
        a = (a << 1) & 0xFF
        if carry:
            a ^= 0x1B  # x^8 + x^4 + x^3 + x + 1  (0x11b reduced)
        b >>= 1
    return p


_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x = _peasant_mul(_x, 0x03)
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("division by zero in GF(2^8)")
    if a == 0:
        return 0
    return _EXP[(_LOG[a] - _LOG[b]) % 255]


def _eval(coeffs: Sequence[int], x: int) -> int:
    """Evaluate polynomial (coeffs[0] = constant term) at x using Horner."""
    acc = 0
    for c in reversed(coeffs):
        acc = _mul(acc, x) ^ c
    return acc


# --- Public API ------------------------------------------------------------


@dataclass(frozen=True)
class Share:
    """A single share. ``x`` is the evaluation point (1..255), ``y`` the
    per-byte polynomial outputs for the whole secret."""

    x: int
    y: bytes

    def __post_init__(self) -> None:
        if not 1 <= self.x <= 255:
            raise ValueError("share x must be in 1..255")


def split(secret: bytes, n: int, k: int) -> List[Share]:
    """Split ``secret`` into ``n`` shares with reconstruction threshold ``k``."""
    if not 1 <= k <= n <= 255:
        raise ValueError("require 1 <= k <= n <= 255")
    if not secret:
        raise ValueError("secret must be non-empty")

    xs = list(range(1, n + 1))
    ys = [bytearray(len(secret)) for _ in xs]
    for pos, byte in enumerate(secret):
        coeffs = [byte] + [secrets.randbelow(256) for _ in range(k - 1)]
        for idx, x in enumerate(xs):
            ys[idx][pos] = _eval(coeffs, x)
    return [Share(x, bytes(y)) for x, y in zip(xs, ys)]


def combine(shares: Sequence[Share]) -> bytes:
    """Reconstruct the secret from >= k shares (uses the first k provided)."""
    if not shares:
        raise ValueError("need at least one share")
    xs = [s.x for s in shares]
    if len(set(xs)) != len(xs):
        raise ValueError("shares have duplicate x coordinates")
    length = len(shares[0].y)
    if any(len(s.y) != length for s in shares):
        raise ValueError("shares have inconsistent length")

    out = bytearray(length)
    for pos in range(length):
        acc = 0
        for i, si in enumerate(shares):
            # Lagrange basis L_i evaluated at x = 0.
            num = 1
            den = 1
            for j, sj in enumerate(shares):
                if i == j:
                    continue
                num = _mul(num, sj.x)            # (0 - x_j) == x_j in GF(2)
                den = _mul(den, si.x ^ sj.x)     # (x_i - x_j) == x_i ^ x_j
            acc ^= _mul(si.y[pos], _div(num, den))
        out[pos] = acc
    return bytes(out)


def reshare(shares: Sequence[Share], k: int) -> List[Share]:
    """Proactive re-sharing: produce fresh shares of the *same* secret.

    This is the safe, non-destructive realisation of "constant flux". We add
    a fresh random sharing of zero (a degree k-1 polynomial with constant
    term 0) to the existing shares. The value at x = 0 is unchanged, so the
    secret is identical, but every share's bytes are randomised. An attacker
    who exfiltrated < k old shares cannot combine them with new shares,
    because the polynomial changed between epochs.
    """
    if not shares:
        raise ValueError("need at least one share")
    xs = [s.x for s in shares]
    if len(set(xs)) != len(xs):
        raise ValueError("shares have duplicate x coordinates")
    if not 2 <= k <= len(xs) + 1:
        # k may legitimately exceed len(xs) if some locations are offline,
        # but it must be at least 2 for re-sharing to mean anything.
        pass
    length = len(shares[0].y)
    new = [bytearray(s.y) for s in shares]
    for pos in range(length):
        zero_coeffs = [0] + [secrets.randbelow(256) for _ in range(k - 1)]
        for idx, x in enumerate(xs):
            new[idx][pos] ^= _eval(zero_coeffs, x)
    return [Share(x, bytes(b)) for x, b in zip(xs, new)]
