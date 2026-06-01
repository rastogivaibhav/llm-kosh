#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v0.3 — the gap (matching), heal, querying, extraction.
Standard library only (no pytest)."""

import shutil
import tempfile
import unittest
from pathlib import Path

import cartridge as c


class V03Test(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-v03-"))
        self.root = self.dir / "CART"
        c.init_cartridge(self.root, "Test Owner")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _meta(self, doc_id):
        return c.parse_frontmatter((self.root / c.find_doc_by_id(self.root, doc_id)).read_text(encoding="utf-8"))[0]

    # ---- THE GAP: TF-IDF correction matching (no [ref:], paraphrased) -------
    def test_paraphrased_correction_matches_via_tfidf(self):
        path = c.add_memory(self.root, "decision", "Recommendation backend store",
                            "Adopt PostgreSQL pgvector for the recommendation ranking backend.",
                            project="MM", quiet=True)
        old_id = c.parse_frontmatter(path.read_text(encoding="utf-8"))[0]["id"]
        rcpt = self.dir / "R.md"
        rcpt.write_text(
            "# MEMORY_RECEIPT\n## Corrections\n"
            "- Replace the recommendation ranking backend store :: move off PostgreSQL pgvector "
            "to a managed vector database service\n",
            encoding="utf-8",
        )
        summary = c.absorb_receipt(self.root, rcpt)
        self.assertEqual(summary["corrections_applied"], 1,
                         "paraphrased correction should match the related decision via TF-IDF")
        self.assertEqual(self._meta(old_id)["status"], "superseded")

    def test_unrelated_correction_stays_open(self):
        c.add_memory(self.root, "decision", "Recommendation backend store",
                     "Adopt PostgreSQL pgvector.", quiet=True)
        rcpt = self.dir / "R.md"
        rcpt.write_text("# MEMORY_RECEIPT\n## Corrections\n- Zebras are striped mammals from Africa\n",
                        encoding="utf-8")
        summary = c.absorb_receipt(self.root, rcpt)
        self.assertEqual(summary["corrections_unmatched"], 1)

    def test_best_match_scoring(self):
        c.add_memory(self.root, "decision", "Use Stripe", "Card payments are processed by Stripe checkout.", quiet=True)
        hit, score = c.best_match(self.root, "Stripe checkout card payments", ["decision"])
        self.assertIsNotNone(hit)
        self.assertGreater(score, 0.18)
        miss, score2 = c.best_match(self.root, "completely orthogonal topic about marathon training", ["decision"])
        self.assertIsNone(miss)

    # ---- QUERYING: re-ranking + filters ------------------------------------
    def test_query_reranks_by_relevance(self):
        c.add_memory(self.root, "decision", "Stripe checkout", "Stripe handles checkout payments.", quiet=True)
        c.add_memory(self.root, "decision", "Adyen note", "Adyen is an alternative provider.", quiet=True)
        c.add_memory(self.root, "note", "Teacher queue", "Teacher approval queue for lessons.", quiet=True)
        res = c.query_memory(self.root, "stripe checkout payments")
        self.assertTrue(res)
        self.assertIn("Stripe", res[0]["title"])
        self.assertIsInstance(res[0]["score"], float)
        if len(res) > 1:
            self.assertGreaterEqual(res[0]["score"], res[-1]["score"])

    def test_query_filters_by_project_and_kind(self):
        c.add_memory(self.root, "decision", "A decision", "shared keyword alpha", project="ProjA", quiet=True)
        c.add_memory(self.root, "note", "B note", "shared keyword alpha", project="ProjB", quiet=True)
        res = c.query_memory(self.root, "alpha", project="ProjA")
        self.assertTrue(all(r["project"] == "ProjA" for r in res))
        res2 = c.query_memory(self.root, "alpha", kinds=["note"])
        self.assertTrue(all(r["kind"] == "note" for r in res2))

    # ---- HEAL: real repairs -------------------------------------------------
    def test_heal_assigns_missing_id_and_type(self):
        (self.root / "source" / "notes" / "orphan.md").write_text(
            "---\ntitle: Orphan\n---\n\n# Orphan\n\nbody text\n", encoding="utf-8")
        c.heal_safe(self.root)
        meta = c.parse_frontmatter((self.root / "source" / "notes" / "orphan.md").read_text(encoding="utf-8"))[0]
        self.assertTrue(meta.get("id"), "heal must assign a missing id")
        self.assertEqual(meta.get("type"), "note", "heal must infer type from folder")

    def test_heal_clears_dangling_superseded_by(self):
        p = c.add_memory(self.root, "decision", "Lonely", "no real superseder", quiet=True)
        rel = str(p.relative_to(self.root))
        c.update_doc_meta(self.root, rel, {"superseded_by": "decision.does-not-exist.0000", "status": "superseded"})
        c.heal_safe(self.root)
        meta = c.parse_frontmatter(p.read_text(encoding="utf-8"))[0]
        self.assertEqual(meta.get("superseded_by", ""), "")
        self.assertEqual(meta.get("status"), "active", "reactivated after clearing a dangling link")

    def test_heal_repairs_supersession_reciprocity(self):
        a = c.add_memory(self.root, "decision", "New way", "the replacement", quiet=True)
        b = c.add_memory(self.root, "decision", "Old way", "the original", quiet=True)
        a_id = c.parse_frontmatter(a.read_text(encoding="utf-8"))[0]["id"]
        b_id = c.parse_frontmatter(b.read_text(encoding="utf-8"))[0]["id"]
        # A claims to supersede B, but B was never updated
        c.update_doc_meta(self.root, str(a.relative_to(self.root)), {"supersedes": b_id})
        c.heal_safe(self.root)
        b_meta = c.parse_frontmatter(b.read_text(encoding="utf-8"))[0]
        self.assertEqual(b_meta.get("superseded_by"), a_id)
        self.assertEqual(b_meta.get("status"), "superseded")

    def test_heal_dry_run_changes_nothing(self):
        (self.root / "source" / "notes" / "orphan.md").write_text(
            "---\ntitle: Orphan\n---\n\n# Orphan\n\nbody\n", encoding="utf-8")
        res = c.heal_safe(self.root, dry_run=True)
        self.assertFalse(res["applied"])
        meta = c.parse_frontmatter((self.root / "source" / "notes" / "orphan.md").read_text(encoding="utf-8"))[0]
        self.assertFalse(meta.get("id"), "dry-run must not write")

    # ---- EXTRACTION: split, dedupe, metadata, binary, chunk ----------------
    def test_ingest_splits_markdown_by_heading(self):
        f = self.dir / "doc.md"
        f.write_text("# One\nalpha body\n\n# Two\nbeta body\n\n# Three\ngamma body\n", encoding="utf-8")
        totals = c.ingest_path(self.root, f)
        self.assertGreaterEqual(totals["added"], 3, "markdown should split into per-heading memories")
        res = c.query_memory(self.root, "beta")
        self.assertTrue(any("Two" in r["title"] for r in res))

    def test_ingest_dedupes_identical_content(self):
        f = self.dir / "same.txt"
        f.write_text("identical content here", encoding="utf-8")
        c.ingest_path(self.root, f)
        totals = c.ingest_path(self.root, f)  # second time
        self.assertEqual(totals["added"], 0)
        self.assertEqual(totals["dupe"], 1)

    def test_ingest_skips_binary(self):
        f = self.dir / "blob.bin"
        f.write_bytes(b"\x00\x01\x02\x03binary")
        totals = c.ingest_path(self.root, f)
        self.assertEqual(totals["added"], 0)
        self.assertEqual(totals["binary"], 1)

    def test_ingest_records_metadata(self):
        f = self.dir / "meta.txt"
        f.write_text("some content for metadata test", encoding="utf-8")
        c.ingest_path(self.root, f)
        res = c.query_memory(self.root, "metadata content")
        rel = res[0]["path"]
        meta = c.parse_frontmatter((self.root / rel).read_text(encoding="utf-8"))[0]
        self.assertTrue(meta.get("source_hash", "").startswith("sha256:"))
        self.assertTrue(meta.get("bytes"))

    def test_ingest_chunks_large_file(self):
        f = self.dir / "big.txt"
        f.write_text(("lorem ipsum dolor sit amet\n" * 600), encoding="utf-8")  # > MAX_CHUNK
        totals = c.ingest_path(self.root, f)
        self.assertGreater(totals["added"], 1, "a large headingless file should be chunked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
