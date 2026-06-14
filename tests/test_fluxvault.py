"""Test suite for FluxVault. Run with:  python -m unittest discover -s tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fluxvault import shamir, aead  # noqa: E402
from fluxvault.audit import AuditLog, AuditEntry, AuditError  # noqa: E402
from fluxvault.leases import LeaseAuthority, LeaseError  # noqa: E402
from fluxvault.store import LocationStore  # noqa: E402
from fluxvault.vault import FluxVault, VaultError  # noqa: E402


class TestShamir(unittest.TestCase):
    def test_round_trip_all_shares(self):
        secret = os.urandom(32)
        shares = shamir.split(secret, 5, 3)
        self.assertEqual(shamir.combine(shares), secret)

    def test_round_trip_exact_threshold(self):
        secret = b"top secret payload key!!!!!!!!!!"
        shares = shamir.split(secret, 5, 3)
        self.assertEqual(shamir.combine(shares[:3]), secret)
        # any combination of k shares works
        self.assertEqual(shamir.combine([shares[0], shares[2], shares[4]]), secret)

    def test_below_threshold_is_wrong(self):
        secret = os.urandom(32)
        shares = shamir.split(secret, 5, 3)
        self.assertNotEqual(shamir.combine(shares[:2]), secret)

    def test_reshare_preserves_secret_and_changes_shares(self):
        secret = os.urandom(32)
        shares = shamir.split(secret, 5, 3)
        new = shamir.reshare(shares, 3)
        # secret unchanged
        self.assertEqual(shamir.combine(new[:3]), secret)
        # but every share's bytes changed (flux happened)
        for old_s, new_s in zip(shares, new):
            self.assertEqual(old_s.x, new_s.x)
            self.assertNotEqual(old_s.y, new_s.y)

    def test_cross_epoch_shares_do_not_combine(self):
        """The security point of flux: old + new shares give garbage."""
        secret = os.urandom(32)
        gen0 = shamir.split(secret, 5, 3)
        gen1 = shamir.reshare(gen0, 3)
        # attacker stole 2 shares in epoch 0, grabs 1 fresh share in epoch 1
        mixed = [gen0[0], gen0[1], gen1[2]]
        self.assertNotEqual(shamir.combine(mixed), secret)

    def test_random_fuzz(self):
        for _ in range(200):
            length = 1 + (os.urandom(1)[0] % 48)
            secret = os.urandom(length)
            n = 3 + (os.urandom(1)[0] % 6)   # 3..8
            k = 2 + (os.urandom(1)[0] % (n - 1))
            shares = shamir.split(secret, n, k)
            picked = shares[:k]
            self.assertEqual(shamir.combine(picked), secret)

    def test_invalid_params(self):
        with self.assertRaises(ValueError):
            shamir.split(b"x", 2, 3)        # k > n
        with self.assertRaises(ValueError):
            shamir.split(b"", 3, 2)         # empty secret


class TestAead(unittest.TestCase):
    def test_seal_open_round_trip(self):
        dek = aead.new_dek()
        pt = b"the quick brown fox" * 100
        blob = aead.seal(dek, pt, b"aad")
        self.assertEqual(aead.open_sealed(dek, blob, b"aad"), pt)

    def test_wrong_key_fails(self):
        blob = aead.seal(aead.new_dek(), b"hi", b"aad")
        with self.assertRaises(Exception):
            aead.open_sealed(aead.new_dek(), blob, b"aad")

    def test_tampered_ciphertext_fails(self):
        dek = aead.new_dek()
        blob = bytearray(aead.seal(dek, b"hello world", b"aad"))
        blob[-1] ^= 0x01
        with self.assertRaises(Exception):
            aead.open_sealed(dek, bytes(blob), b"aad")

    def test_wrong_aad_fails(self):
        dek = aead.new_dek()
        blob = aead.seal(dek, b"hello", b"aad-1")
        with self.assertRaises(Exception):
            aead.open_sealed(dek, blob, b"aad-2")


class TestLeases(unittest.TestCase):
    def test_valid_lease(self):
        auth = LeaseAuthority()
        lease = auth.issue("alice", "vault-1", ttl_seconds=60)
        auth.verify(lease, "alice", "vault-1")  # should not raise

    def test_expired_lease(self):
        t = {"now": 1000.0}
        auth = LeaseAuthority(clock=lambda: t["now"])
        lease = auth.issue("alice", "vault-1", ttl_seconds=10)
        t["now"] = 1011.0
        with self.assertRaises(LeaseError):
            auth.verify(lease, "alice", "vault-1")

    def test_forged_lease(self):
        auth = LeaseAuthority()
        other = LeaseAuthority()
        lease = other.issue("alice", "vault-1", ttl_seconds=60)
        with self.assertRaises(LeaseError):
            auth.verify(lease, "alice", "vault-1")

    def test_subject_or_vault_mismatch(self):
        auth = LeaseAuthority()
        lease = auth.issue("alice", "vault-1", ttl_seconds=60)
        with self.assertRaises(LeaseError):
            auth.verify(lease, "bob", "vault-1")
        with self.assertRaises(LeaseError):
            auth.verify(lease, "alice", "vault-2")


class TestAudit(unittest.TestCase):
    def test_clean_chain_verifies(self):
        log = AuditLog()
        log.append("a", {"x": 1})
        log.append("b", {"y": 2})
        log.verify()  # no raise

    def test_modified_entry_detected(self):
        log = AuditLog()
        log.append("a", {"x": 1})
        log.append("b", {"y": 2})
        # tamper with stored detail of entry 0
        bad = AuditEntry(
            index=log.entries[0].index,
            timestamp=log.entries[0].timestamp,
            event=log.entries[0].event,
            detail={"x": 999},
            prev_hash=log.entries[0].prev_hash,
            this_hash=log.entries[0].this_hash,
        )
        log._entries[0] = bad
        with self.assertRaises(AuditError):
            log.verify()

    def test_deleted_entry_detected(self):
        log = AuditLog()
        log.append("a")
        log.append("b")
        log.append("c")
        del log._entries[1]
        with self.assertRaises(AuditError):
            log.verify()


class TestEndToEnd(unittest.TestCase):
    def _build(self, n=5, k=3):
        store = LocationStore([f"loc-{i}" for i in range(n)])
        auth = LeaseAuthority()
        vault = FluxVault("vault-1", n, k, store, auth, AuditLog())
        return vault, auth

    def test_store_and_retrieve(self):
        vault, auth = self._build()
        secret = b"medical records: patient 42"
        vault.store_data(secret)
        lease = auth.issue("dr-house", "vault-1", ttl_seconds=60)
        self.assertEqual(vault.retrieve("dr-house", lease), secret)

    def test_retrieve_requires_valid_lease(self):
        vault, auth = self._build()
        vault.store_data(b"data")
        bad = LeaseAuthority().issue("dr-house", "vault-1", ttl_seconds=60)
        with self.assertRaises(LeaseError):
            vault.retrieve("dr-house", bad)

    def test_survives_location_loss(self):
        vault, auth = self._build(n=5, k=3)
        secret = b"survive the apocalypse"
        vault.store_data(secret)
        # knock out 2 of 5 locations: still have k=3 shares + a ciphertext replica
        vault.store.set_online("loc-0", False)
        vault.store.set_online("loc-1", False)
        lease = auth.issue("alice", "vault-1", ttl_seconds=60)
        self.assertEqual(vault.retrieve("alice", lease), secret)

    def test_quorum_loss_denies_but_does_not_destroy(self):
        vault, auth = self._build(n=5, k=3)
        secret = b"still here"
        vault.store_data(secret)
        for i in range(3):  # only 2 online -> below k
            vault.store.set_online(f"loc-{i}", False)
        lease = auth.issue("alice", "vault-1", ttl_seconds=60)
        with self.assertRaises(VaultError):
            vault.retrieve("alice", lease)
        # bring them back -> data was NOT destroyed (the key difference from
        # the self-destruct design)
        for i in range(3):
            vault.store.set_online(f"loc-{i}", True)
        self.assertEqual(vault.retrieve("alice", lease), secret)

    def test_flux_then_retrieve(self):
        vault, auth = self._build()
        secret = b"data in constant flux"
        vault.store_data(secret)
        for _ in range(20):  # 20 epochs of resharing
            vault.flux()
        lease = auth.issue("alice", "vault-1", ttl_seconds=60)
        self.assertEqual(vault.retrieve("alice", lease), secret)

    def test_rotate_then_retrieve(self):
        vault, auth = self._build()
        secret = b"rotate my key please"
        vault.store_data(secret)
        old_blob = vault.store.any_ciphertext()
        vault.rotate()
        new_blob = vault.store.any_ciphertext()
        self.assertNotEqual(old_blob, new_blob)  # bulk really re-encrypted
        lease = auth.issue("alice", "vault-1", ttl_seconds=60)
        self.assertEqual(vault.retrieve("alice", lease), secret)

    def test_audit_chain_after_operations(self):
        vault, auth = self._build()
        vault.store_data(b"x")
        vault.flux()
        vault.rotate()
        lease = auth.issue("alice", "vault-1", ttl_seconds=60)
        vault.retrieve("alice", lease)
        vault.audit.verify()
        self.assertGreaterEqual(len(vault.audit), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
