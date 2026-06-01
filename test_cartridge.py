#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v0.2 — standard library only (no pytest)."""

import shutil
import tempfile
import unittest
from pathlib import Path

import cartridge as c


class CartridgeTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-test-"))
        self.root = self.dir / "CART"
        c.init_cartridge(self.root, "Test Owner")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    # -- basics ---------------------------------------------------------------
    def test_init_creates_structure(self):
        self.assertTrue((self.root / "CARTRIDGE.json").exists())
        self.assertTrue((self.root / "BOOT.md").exists())
        self.assertTrue((self.root / "source" / "corrections").is_dir())

    def test_add_and_query_roundtrip(self):
        c.add_memory(self.root, "project", "SelectiveOS", "UK 11+ prep platform.", quiet=True)
        res = c.query_memory(self.root, "SelectiveOS prep")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "SelectiveOS")
        self.assertTrue(res[0]["snippet"])  # snippet is no longer None

    def test_query_handles_fts_operator_words(self):
        c.add_memory(self.root, "note", "creds note", "database creds are rotated", quiet=True)
        # "NEAR" and "OR" are FTS operators; must not raise and must still match
        res = c.query_memory(self.root, "NEAR creds OR rotated")
        self.assertTrue(any("creds" in r["title"] for r in res))

    # -- the v0.2 core: absorb produces typed memories ------------------------
    def test_absorb_creates_typed_decision_with_provenance(self):
        rcpt = self.dir / "R1.md"
        rcpt.write_text(
            "# MEMORY_RECEIPT\n"
            "## New decisions\n"
            "- Use Adyen for payments :: Replaces Stripe; better UK fees [project: SelectiveOS]\n",
            encoding="utf-8",
        )
        c.absorb_receipt(self.root, rcpt)
        res = c.query_memory(self.root, "Adyen payments", kinds=["decision"])
        self.assertEqual(len(res), 1, "absorb must create a typed decision, not an opaque blob")
        self.assertEqual(res[0]["kind"], "decision")
        self.assertEqual(res[0]["project"], "SelectiveOS")
        self.assertTrue(res[0]["source_receipt"].startswith("receipt."),
                        "decision must carry provenance back to its receipt")

    # -- supersession via explicit ref ---------------------------------------
    def test_correction_with_ref_supersedes_target(self):
        path = c.add_memory(self.root, "decision", "Use Stripe", "Payments via Stripe.", quiet=True)
        meta, _ = c.parse_frontmatter(path.read_text(encoding="utf-8"))
        old_id = meta["id"]

        rcpt = self.dir / "R2.md"
        rcpt.write_text(
            "# MEMORY_RECEIPT\n"
            "## Corrections\n"
            f"- Stripe replaced by Adyen :: switched provider [ref: {old_id}]\n",
            encoding="utf-8",
        )
        summary = c.absorb_receipt(self.root, rcpt)
        self.assertEqual(summary["corrections_applied"], 1)

        # old decision is now superseded and has a backlink
        old_meta, _ = c.parse_frontmatter((self.root / c.find_doc_by_id(self.root, old_id)).read_text(encoding="utf-8"))
        self.assertEqual(old_meta["status"], "superseded")
        self.assertTrue(old_meta.get("superseded_by"))
        # old file still exists (non-destructive / reversible)
        self.assertIsNotNone(c.find_doc_by_id(self.root, old_id))

    def test_correction_without_match_left_open(self):
        rcpt = self.dir / "R3.md"
        rcpt.write_text(
            "# MEMORY_RECEIPT\n## Corrections\n- Totally unrelated correction about zebras\n",
            encoding="utf-8",
        )
        summary = c.absorb_receipt(self.root, rcpt)
        self.assertEqual(summary["corrections_unmatched"], 1)

    # -- superseded memories are excluded from packs by default ---------------
    def test_pack_excludes_superseded(self):
        path = c.add_memory(self.root, "decision", "Use Stripe", "Payments via Stripe.", quiet=True)
        old_id = c.parse_frontmatter(path.read_text(encoding="utf-8"))[0]["id"]
        rcpt = self.dir / "R4.md"
        rcpt.write_text(f"# MEMORY_RECEIPT\n## Corrections\n- Use Adyen now [ref: {old_id}]\n", encoding="utf-8")
        c.absorb_receipt(self.root, rcpt)

        out = self.dir / "pack.zip"
        c.pack_context(self.root, "Stripe payments", "chatgpt", out, include_private=True)
        import zipfile
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
            blob = "".join(zf.read(n).decode("utf-8", "replace") for n in names if n.endswith(".md"))
        # the retired Stripe decision should not appear as an active matched source file
        self.assertNotIn("Payments via Stripe.", blob)

    # -- secret gate at the pack boundary ------------------------------------
    def test_pack_blocks_on_secret(self):
        c.add_memory(self.root, "decision", "DB creds", "production password: hunter2xyz",
                     visibility="private", quiet=True)
        out = self.dir / "leak.zip"
        with self.assertRaises(SystemExit) as ctx:
            c.pack_context(self.root, "creds DB", "chatgpt", out, include_private=True)
        self.assertEqual(ctx.exception.code, 2)
        self.assertFalse(out.exists(), "blocked pack must not be written")

    def test_pack_redacts_secret_and_leaves_source_intact(self):
        src = c.add_memory(self.root, "decision", "DB creds",
                           "token=ghp_abcdefghijklmnopqrstuvwxyz0123", visibility="private", quiet=True)
        out = self.dir / "safe.zip"
        c.pack_context(self.root, "creds DB token", "chatgpt", out, include_private=True, redact=True)
        import zipfile
        with zipfile.ZipFile(out) as zf:
            blob = "".join(zf.read(n).decode("utf-8", "replace") for n in zf.namelist() if n.endswith(".md"))
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz0123", blob)
        self.assertIn("REDACTED", blob)
        # source file on disk is unchanged — still contains the original secret
        self.assertIn("ghp_abcdefghijklmnopqrstuvwxyz0123", src.read_text(encoding="utf-8"))

    # -- incremental index ----------------------------------------------------
    def test_index_skips_rebuild_when_corpus_unchanged(self):
        c.add_memory(self.root, "note", "n1", "body one", quiet=True)
        self.assertFalse(c.rebuild_index(self.root), "no change -> no rebuild")
        c.add_memory(self.root, "note", "n2", "body two", quiet=True, reindex=False)
        self.assertTrue(c.rebuild_index(self.root), "corpus changed -> rebuild happens")

    # -- audit now catches secrets in private source too ----------------------
    def test_audit_flags_secret_in_private_source(self):
        c.add_memory(self.root, "note", "secret note", "api_key: sk_live_abcdef0123456789xyz",
                     visibility="private", quiet=True)
        report = c.audit(self.root)
        self.assertTrue(any(i["type"] == "secret_in_source" for i in report["issues"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
