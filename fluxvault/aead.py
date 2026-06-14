"""Authenticated envelope encryption.

The *data* is sealed once with a random 256-bit data-encryption key (DEK).
The DEK — small, fixed size — is what gets threshold-split and kept in flux.
This is standard envelope encryption: we never re-encrypt the bulk data just
to rotate protection; we rotate/reshare the key instead.

Primitive selection
-------------------
We prefer **AES-256-GCM** from the ``cryptography`` package. If that package
is unavailable or broken in the runtime (it ships a native extension that is
not always importable), we transparently fall back to a **stdlib-only**
encrypt-then-MAC AEAD: a SHA-256 counter-mode keystream authenticated with
HMAC-SHA256, with the encryption and MAC keys separated via HKDF. Both modes
are authenticated; the envelope records which one produced it so decryption
always uses the matching primitive.

NOTE ON QUANTUM RESISTANCE
--------------------------
AES-256 is considered quantum-resistant for confidentiality (Grover only
halves the effective key strength -> ~128-bit security). The quantum-fragile
part of a real system is the *asymmetric* key wrapping used to deliver the
DEK to a client. In production you would wrap the DEK with a hybrid KEM
(e.g. X25519 + ML-KEM-768). That hybrid wrap is out of scope here; the
envelope is structured so the DEK-delivery step is the single place it lands.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

DEK_BYTES = 32   # 256-bit
NONCE_BYTES = 12

# Envelope mode markers (first byte of the blob).
_MODE_AESGCM = b"\x01"
_MODE_STDLIB = b"\x02"

try:  # pragma: no cover - depends on runtime
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM

    _AESGCM(os.urandom(32)).encrypt(os.urandom(12), b"", None)  # smoke test
    _HAVE_AESGCM = True
except Exception:  # broken native ext, missing package, etc.
    _HAVE_AESGCM = False


def primitive() -> str:
    """Name of the AEAD primitive actually in use (for diagnostics/audit)."""
    return "AES-256-GCM" if _HAVE_AESGCM else "SHA256-CTR+HMAC (stdlib)"


def new_dek() -> bytes:
    return os.urandom(DEK_BYTES)


# --- stdlib fallback AEAD --------------------------------------------------


def _hkdf(key: bytes, info: bytes, length: int) -> bytes:
    prk = hmac.new(b"FluxVault-salt", key, hashlib.sha256).digest()
    out, t, counter = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


def _ctr_keystream(enc_key: bytes, nonce: bytes, n: int) -> bytes:
    out, counter = bytearray(), 0
    while len(out) < n:
        out += hashlib.sha256(enc_key + nonce + counter.to_bytes(8, "big")).digest()
        counter += 1
    return bytes(out[:n])


def _stdlib_seal(dek: bytes, plaintext: bytes, aad: bytes) -> bytes:
    enc_key = _hkdf(dek, b"enc", 32)
    mac_key = _hkdf(dek, b"mac", 32)
    nonce = os.urandom(NONCE_BYTES)
    ks = _ctr_keystream(enc_key, nonce, len(plaintext))
    ct = bytes(a ^ b for a, b in zip(plaintext, ks))
    tag = hmac.new(mac_key, aad + nonce + ct, hashlib.sha256).digest()
    return _MODE_STDLIB + nonce + tag + ct


def _stdlib_open(dek: bytes, blob: bytes, aad: bytes) -> bytes:
    nonce = blob[1 : 1 + NONCE_BYTES]
    tag = blob[1 + NONCE_BYTES : 1 + NONCE_BYTES + 32]
    ct = blob[1 + NONCE_BYTES + 32 :]
    mac_key = _hkdf(dek, b"mac", 32)
    expected = hmac.new(mac_key, aad + nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, tag):
        raise ValueError("authentication failed (tampered or wrong key)")
    enc_key = _hkdf(dek, b"enc", 32)
    ks = _ctr_keystream(enc_key, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks))


# --- public API ------------------------------------------------------------


def seal(dek: bytes, plaintext: bytes, aad: Optional[bytes] = None) -> bytes:
    if len(dek) != DEK_BYTES:
        raise ValueError("DEK must be 32 bytes")
    aad = aad or b""
    if _HAVE_AESGCM:
        nonce = os.urandom(NONCE_BYTES)
        ct = _AESGCM(dek).encrypt(nonce, plaintext, aad)
        return _MODE_AESGCM + nonce + ct
    return _stdlib_seal(dek, plaintext, aad)


def open_sealed(dek: bytes, blob: bytes, aad: Optional[bytes] = None) -> bytes:
    if len(dek) != DEK_BYTES:
        raise ValueError("DEK must be 32 bytes")
    aad = aad or b""
    mode = blob[:1]
    if mode == _MODE_AESGCM:
        if not _HAVE_AESGCM:
            raise ValueError("blob needs AES-GCM but it is unavailable here")
        nonce = blob[1 : 1 + NONCE_BYTES]
        ct = blob[1 + NONCE_BYTES :]
        return _AESGCM(dek).decrypt(nonce, ct, aad)
    if mode == _MODE_STDLIB:
        return _stdlib_open(dek, blob, aad)
    raise ValueError("unknown envelope mode")
