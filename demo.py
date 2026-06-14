#!/usr/bin/env python3
"""End-to-end FluxVault demo.

Run:  python demo.py
"""

from fluxvault import FluxVault, LocationStore, LeaseAuthority, AuditLog


def banner(t):
    print("\n" + "=" * 60 + f"\n{t}\n" + "=" * 60)


def main():
    n, k = 5, 3
    secret = b"PATIENT 42 | dx: confidential | ssn: 000-00-0000"

    banner(f"1. Provision a {k}-of-{n} vault across separate locations")
    store = LocationStore([f"region-{i}" for i in range(n)])
    auth = LeaseAuthority()
    vault = FluxVault("vault-patient-42", n, k, store, auth, AuditLog())
    vault.store_data(secret)
    print(f"   stored {len(secret)} bytes, sealed with AES-256-GCM")
    print(f"   data key split into {n} shares (need any {k} to recover)")

    banner("2. 'Constant flux': reshare the key every epoch")
    before = [store._locs[lid].share.y[:6].hex() for lid in store.location_ids]
    for _ in range(5):
        vault.flux()
    after = [store._locs[lid].share.y[:6].hex() for lid in store.location_ids]
    for lid, b, a in zip(store.location_ids, before, after):
        print(f"   {lid}: {b}.. -> {a}..   (share churned; secret unchanged)")

    banner("3. Lose 2 of 5 locations (failure or attack on one node)")
    store.set_online("region-0", False)
    store.set_online("region-1", False)
    print(f"   online locations: {store.online_count()}/{n}")

    banner("4. Authorised retrieval inside a time-boxed lease")
    lease = auth.issue("dr-house", "vault-patient-42", ttl_seconds=30)
    got = vault.retrieve("dr-house", lease)
    print(f"   recovered: {got.decode()}")
    assert got == secret

    banner("5. Attacker without a valid lease is refused")
    forged = LeaseAuthority().issue("dr-house", "vault-patient-42", 30)
    try:
        vault.retrieve("dr-house", forged)
    except Exception as e:
        print(f"   denied: {type(e).__name__}: {e}")

    banner("6. Drop below quorum: access denied, data NOT destroyed")
    store.set_online("region-2", False)
    print(f"   online locations: {store.online_count()}/{n} (< k={k})")
    try:
        vault.retrieve("dr-house", lease)
    except Exception as e:
        print(f"   denied: {type(e).__name__}: {e}")
    for i in range(3):
        store.set_online(f"region-{i}", True)
    again = vault.retrieve("dr-house", lease)
    print(f"   locations restored -> data recovered: {again.decode()[:24]}...")
    assert again == secret

    banner("7. Tamper-evident audit log")
    vault.audit.verify()
    print(f"   {len(vault.audit)} entries, hash chain intact:")
    for e in vault.audit.entries:
        print(f"     #{e.index} {e.event:16} {e.this_hash[:12]}..")

    print("\nAll demo assertions passed.\n")


if __name__ == "__main__":
    main()
