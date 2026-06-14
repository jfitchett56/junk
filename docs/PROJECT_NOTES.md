# FluxVault — Project Notes

**Status:** ⏸️ ON HOLD as of 2026-06-14
**Reason:** Idea is technically sound and the PoC works, but market demand is
unproven. Parked rather than killed — pick back up if a real need appears.

---

## The idea (one paragraph)

A vault where stored data is encrypted, the protecting key is kept in constant
flux (continuously re-randomized), the secret is spread across multiple
locations so losing one loses nothing, and access is granted only through
short-lived, credential-gated time windows.

## What was decided

- **Build a proof of concept** to test whether the idea is buildable with sound
  primitives. ✅ Done — it is.
- **Drop the "tampering destroys the data" mechanism.** A self-destruct storage
  substrate turns ordinary failures (power loss, bugs, network partitions) into
  permanent data loss and fights the redundancy goal. Replaced with
  **tamper-evident detection** (hash-chained audit log) instead of destruction.
- **Put it on hold.** Not convinced there is a market yet. No further work
  planned until that changes.

## What exists in this repo

- `fluxvault/` — working library (Shamir threshold sharing + proactive
  re-sharing, envelope encryption with AES-256-GCM and a stdlib fallback,
  short-lived leases, tamper-evident audit log, multi-location store sim).
- `tests/` — 25 tests, all passing on both crypto paths.
- `demo.py` — runnable end-to-end walkthrough.
- `README.md` — architecture and the idea→implementation mapping.

Verify it still runs:

```bash
python -m unittest discover -s tests -v
python demo.py
```

## Why it's on hold, not abandoned

The technical risk is low; the **market risk is the open question**. Before
investing more, we'd want evidence of demand — e.g. a customer or regulation
that specifically needs moving-target key protection with multi-location
threshold recovery, beyond what a standard KMS/HSM already offers.

## Open questions to revisit if resumed

1. **Who is the buyer?** What concrete use case isn't already served by AWS KMS,
   HashiCorp Vault, or an HSM? (This is the gating question.)
2. **Post-quantum key delivery** — the one real crypto gap. Needs a hybrid KEM
   (X25519 + ML-KEM-768); the environment lacked a PQC-capable library.
3. **Threshold decryption / MPC** — so the full key is never reassembled in a
   single process. Current PoC reconstructs in one place.
4. **Real independent locations** — separate trust/failure domains, not
   in-memory objects.
5. **Cost/benefit of "flux"** — how often is re-sharing actually worth it vs.
   plain periodic key rotation?

## How to resume

1. Re-read `README.md` ("Honest limitations") and the open questions above.
2. Start with question #1 (market) before any further engineering.
3. If green-lit, tackle PQC key-wrap first — it's the highest-value gap.
