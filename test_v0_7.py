#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v0.7 — safety, partitions, shareability.
Leakage prevention is the core concern. Standard library only."""

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import cartridge as c


class V07Test(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-v07-"))
        self.root = self.dir / "CART"
        c.init_cartridge(self.root, "Test Owner")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _id(self, p):
        return c.parse_frontmatter(p.read_text(encoding="utf-8"))[0]["id"]

    def _pack_blob(self, zp):
        with zipfile.ZipFile(zp) as zf:
            return "".join(zf.read(n).decode("utf-8", "replace") for n in zf.namelist()
                           if n.endswith((".md", ".json", ".txt")))

    def _quiet(self, fn, *a, **k):
        with redirect_stdout(io.StringIO()):
            return fn(*a, **k)

    # ---- policy ------------------------------------------------------------
    def test_policy_defaults_without_file(self):
        pol = self._quiet(c.load_policy, self.root)
        self.assertEqual(pol["default_visibility"], "private")
        self.assertTrue(pol["require_redaction"])

    def test_policy_init_writes_file(self):
        self._quiet(c.policy_cmd, self.root, init=True)
        self.assertTrue((self.root / "CARTRIDGE_POLICY.json").exists())

    def test_policy_file_overrides_defaults(self):
        c.write_json(self.root / "CARTRIDGE_POLICY.json",
                     {"allowed_export_visibility": ["public"]})
        pol = c.load_policy(self.root)
        self.assertEqual(pol["allowed_export_visibility"], ["public"])
        self.assertTrue(pol["require_redaction"])  # still merged from defaults

    # ---- classify ----------------------------------------------------------
    def test_classify_suggests_but_does_not_apply(self):
        p = c.add_memory(self.root, "note", "Creds note", "the api key is here: x",
                         visibility="shareable", quiet=True)
        res = self._quiet(c.classify, self.root, apply=False)
        self.assertTrue(res["suggestions"])
        meta = c.parse_frontmatter(p.read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["visibility"], "shareable", "suggest-only must not change anything")

    def test_classify_apply_changes_visibility(self):
        p = c.add_memory(self.root, "note", "Creds note", "password: secretvalue123",
                         visibility="shareable", quiet=True)
        self._quiet(c.classify, self.root, apply=True)
        meta = c.parse_frontmatter(p.read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["visibility"], "private")

    # ---- partition ---------------------------------------------------------
    def test_partition_buckets(self):
        c.add_memory(self.root, "note", "a", "x", visibility="private", quiet=True)
        c.add_memory(self.root, "note", "b", "x", visibility="shareable", quiet=True)
        c.add_memory(self.root, "note", "c", "x", visibility="blocked", quiet=True)
        res = self._quiet(c.partition, self.root)
        parts = res["partitions"]
        self.assertEqual(len(parts["private"]), 1)
        self.assertEqual(len(parts["shareable"]), 1)
        self.assertEqual(len(parts["blocked"]), 1)

    # ---- quarantine --------------------------------------------------------
    def test_quarantine_and_restore_nondestructive(self):
        p = c.add_memory(self.root, "note", "risky", "x", visibility="shareable", quiet=True)
        did = self._id(p)
        self._quiet(c.quarantine, self.root, doc_id=did)
        meta = c.parse_frontmatter(p.read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["visibility"], "quarantine")
        self.assertTrue(p.exists(), "quarantine must not delete the file")
        self._quiet(c.quarantine, self.root, doc_id=did, restore=True)
        meta = c.parse_frontmatter(p.read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["visibility"], "shareable", "restore returns prior visibility")

    def test_quarantined_item_never_exported(self):
        c.add_memory(self.root, "note", "secret topic alpha", "shareable body alpha",
                     visibility="shareable", quiet=True)
        p = c.add_memory(self.root, "note", "secret topic alpha two", "another alpha body",
                         visibility="shareable", quiet=True)
        self._quiet(c.quarantine, self.root, doc_id=self._id(p))
        out = self.dir / "q.zip"
        self._quiet(c.pack_context, self.root, "alpha", "chatgpt", out, include_private=False)
        blob = self._pack_blob(out)
        self.assertNotIn("another alpha body", blob, "quarantined content must not leak")

    # ---- LEAKAGE PREVENTION (the point of v0.7) ----------------------------
    def test_safe_pack_excludes_private(self):
        c.add_memory(self.root, "decision", "Public thing", "shareable detail about alpha",
                     visibility="shareable", quiet=True)
        c.add_memory(self.root, "decision", "Private thing", "PRIVATESECRETBODY about alpha",
                     visibility="private", quiet=True)
        out = self.dir / "safe.zip"
        self._quiet(c.safe_pack, self.root, "alpha", "chatgpt", out)
        blob = self._pack_blob(out)
        self.assertNotIn("PRIVATESECRETBODY", blob, "private must never leave via safe-pack")

    def test_safe_pack_excludes_blocked(self):
        c.add_memory(self.root, "decision", "Blocked thing", "BLOCKEDBODY about beta",
                     visibility="blocked", quiet=True)
        c.add_memory(self.root, "decision", "Open thing", "shareable beta detail",
                     visibility="shareable", quiet=True)
        out = self.dir / "safe2.zip"
        self._quiet(c.safe_pack, self.root, "beta", "chatgpt", out)
        self.assertNotIn("BLOCKEDBODY", self._pack_blob(out))

    def test_blocked_never_exported_by_default_pack(self):
        c.add_memory(self.root, "decision", "Blocked thing", "BLOCKEDBODY gamma",
                     visibility="blocked", quiet=True)
        out = self.dir / "p.zip"
        # even with include_private, blocked is withheld unless allow_blocked
        self._quiet(c.pack_context, self.root, "gamma", "chatgpt", out, include_private=True)
        self.assertNotIn("BLOCKEDBODY", self._pack_blob(out))

    def test_allow_blocked_includes_blocked(self):
        c.add_memory(self.root, "decision", "Blocked thing", "BLOCKEDBODY delta",
                     visibility="blocked", quiet=True)
        out = self.dir / "pb.zip"
        self._quiet(c.pack_context, self.root, "delta", "chatgpt", out,
                    include_private=True, allow_blocked=True)
        self.assertIn("BLOCKEDBODY", self._pack_blob(out))

    def test_policy_enforced_filters_disallowed_visibility(self):
        c.write_json(self.root / "CARTRIDGE_POLICY.json",
                     {"allowed_export_visibility": ["public"]})
        c.add_memory(self.root, "decision", "Workish", "WORKSAFEBODY epsilon",
                     visibility="work-safe", quiet=True)
        out = self.dir / "pol.zip"
        # work-safe normally exportable, but policy only allows 'public'
        self._quiet(c.pack_context, self.root, "epsilon", "chatgpt", out,
                    include_private=False, enforce_policy=True)
        self.assertNotIn("WORKSAFEBODY", self._pack_blob(out))

    def test_policy_decisions_logged(self):
        c.add_memory(self.root, "decision", "Blocked thing", "BLOCKEDBODY zeta",
                     visibility="blocked", quiet=True)
        out = self.dir / "log.zip"
        self._quiet(c.pack_context, self.root, "zeta", "chatgpt", out, include_private=True)
        events = [json.loads(l) for l in (self.root / "ledger" / "events.jsonl").read_text().splitlines()]
        self.assertTrue(any(e["event"] == "policy.export_filtered" for e in events))

    def test_safe_pack_redacts_secret_in_shareable(self):
        # a shareable doc that still contains a secret must be redacted by safe-pack
        c.add_memory(self.root, "note", "leak", "token=ghp_abcdefghijklmnop12345 about eta",
                     visibility="shareable", quiet=True)
        out = self.dir / "sr.zip"
        self._quiet(c.safe_pack, self.root, "eta", "chatgpt", out)
        self.assertNotIn("ghp_abcdefghijklmnop12345", self._pack_blob(out))


if __name__ == "__main__":
    unittest.main(verbosity=2)
