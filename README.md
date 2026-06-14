# FluxVault — moving-target data protection (proof of concept)

> ⏸️ **ON HOLD (2026-06-14).** Parked pending market validation — see
> [`docs/PROJECT_NOTES.md`](docs/PROJECT_NOTES.md). The code works and tests
> pass; no further development is planned for now.

A small, self-contained PoC of the **safe** version of an idea: store data so
that its protection is in constant flux and is spread across multiple
locations, *without* the self-destruct mechanism that makes the naive version
dangerous.

> **Status:** educational proof of concept. It demonstrates that the goals are
> achievable with standard, reviewable primitives. It is **not** production
> crypto — see *Honest limitations* below.

## The original idea, and what changed

| Original idea | What this PoC does instead | Why |
|---|---|---|
| Re-encrypt all data with new keys every few seconds | **Proactive re-sharing** of the data key every epoch (`flux()`), plus optional full re-encryption on a slower cadence (`rotate()`) | Churning a key share is cheap and gives the real benefit (shrinking the window any single key/share is useful); re-encrypting bulk data every few seconds is mostly wasted I/O and doesn't make the cipher harder to break |
| Any attempt to stop it **destroys** the data | **Tamper-EVIDENT** hash-chained audit log; detection drives alerting + rotation | A destroy-on-interference store turns power blips, bugs and partitions into permanent data loss, and fights your own redundancy goal |
| Data kept in multiple locations; survive losing one | **Shamir k-of-n threshold sharing** of the key + replicated ciphertext | Lose up to `n-k` locations and still recover; fewer than `k` shares reveal *nothing* (information-theoretic) |
| Time window + credentials to request data | **Short-lived HMAC-signed leases** | Access is authenticated and inherently temporary |
| Data downloaded still encrypted, needs current key | **Envelope encryption**: data sealed with a DEK; the DEK is what's shared | Standard KMS pattern |
| Resist AI/quantum | **AES-256-GCM** (quantum-OK for confidentiality); structured for a hybrid PQC key-wrap drop-in | The real quantum risk is *asymmetric* key delivery — see below |

## Layout

```
fluxvault/
  shamir.py   GF(2^8) Shamir split/combine + proactive reshare ("flux")
  aead.py     envelope encryption: AES-256-GCM, stdlib fallback
  leases.py   short-lived, HMAC-signed access leases (the "time window")
  audit.py    hash-chained tamper-evident log (replaces self-destruct)
  store.py    multi-location store: replicated ciphertext + one share each
  vault.py    orchestration: store / flux / rotate / retrieve
demo.py       runnable end-to-end walkthrough
tests/        25 unit + property + end-to-end tests
```

## Run it

```bash
pip install -r requirements.txt      # optional; falls back to stdlib if absent
python demo.py
python -m unittest discover -s tests -v
```

## Honest limitations (read before trusting this)

- **Not production crypto.** Use a vetted KMS/HSM. The stdlib fallback AEAD is
  a sound construction but exists only so the demo runs with no dependencies.
- **No real post-quantum yet.** AES-256 is fine against quantum for
  confidentiality, but a real system must deliver the DEK to clients via a
  hybrid KEM (X25519 + ML-KEM-768). That wrap is the single quantum-fragile
  spot and is intentionally stubbed here (the installed `cryptography` predates
  ML-KEM). This is the most important gap.
- **Single-process simulation.** "Locations" are in-memory objects. Real
  security needs genuinely independent failure/trust domains and a secure
  reshare protocol so a single compromised coordinator can't see `k` shares at
  reconstruction time. Reconstruction here happens in one process — a real
  deployment would want MPC/threshold decryption so the full key is never
  reassembled in one place.
- **Flux ≠ stronger cipher.** Re-sharing limits the value of a *stolen share*
  across epochs; it does **not** make AES harder to break. If the cipher
  itself falls, flux does not save you. The defense is PQC + key hygiene.
- **Availability vs. secrecy is a real tradeoff.** Replicating ciphertext to
  every location maximizes availability but widens the attack surface for the
  ciphertext blob. The security rests on the key shares, not on hiding the
  ciphertext.
