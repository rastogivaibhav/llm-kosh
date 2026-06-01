#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v0.4 — resolve + embeddings/vector index.
Standard library only (no pytest). The dense ('st') backend is exercised with a
stub embedder so no model download is needed."""

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import cartridge as c


class FakeEmbedder:
    """Deterministic 3-dim dense embedder for testing the non-tfidf path."""
    name = "st"
    model_name = "fake-mini"
    VOCAB = ["stripe", "adyen", "teacher"]

    def embed_many(self, texts):
        out = []
        for t in texts:
            tl = (t or "").lower()
            out.append([1.0 if w in tl else 0.0 for w in self.VOCAB])
        return out

    def embed(self, text):
        return self.embed_many([text])[0]


class V04Test(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-v04-"))
        self.root = self.dir / "CART"
        c.init_cartridge(self.root, "Test Owner")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _id(self, path):
        return c.parse_frontmatter(path.read_text(encoding="utf-8"))[0]["id"]

    # ---- embeddings / vector DB (tfidf, offline) ---------------------------
    def test_build_vector_index_tfidf(self):
        c.add_memory(self.root, "decision", "Stripe checkout", "Stripe processes checkout payments.", quiet=True)
        c.add_memory(self.root, "note", "Teacher queue", "Teacher approval queue.", quiet=True)
        info = c.build_vector_index(self.root, backend="tfidf")
        self.assertEqual(info["count"], 2)
        self.assertGreater(info["dim"], 0)
        meta = c._vmeta(self.root)
        self.assertEqual(meta["backend"], "tfidf")
        self.assertEqual(meta["count"], 2)

    def test_semantic_search_tfidf_ranks_relevant_first(self):
        c.add_memory(self.root, "decision", "Stripe checkout", "Stripe processes checkout payments.", quiet=True)
        c.add_memory(self.root, "note", "Marathon plan", "Couch to 5k running schedule.", quiet=True)
        c.build_vector_index(self.root, backend="tfidf")
        res = c.semantic_search(self.root, "stripe checkout payment")
        self.assertTrue(res)
        self.assertIn("Stripe", res[0]["title"])
        self.assertIsInstance(res[0]["score"], float)

    def test_semantic_search_with_stub_dense_backend(self):
        c.add_memory(self.root, "decision", "Stripe checkout", "Stripe payments.", quiet=True)
        c.add_memory(self.root, "note", "Adyen note", "Adyen provider.", quiet=True)
        c.add_memory(self.root, "note", "Teacher queue", "Teacher approval.", quiet=True)
        import ai_cartridge.engine.search as search_mod
        orig = search_mod.get_embedder
        search_mod.get_embedder = lambda backend, model="x": FakeEmbedder()
        self.addCleanup(lambda: setattr(search_mod, "get_embedder", orig))
        info = c.build_vector_index(self.root, backend="st", model="fake-mini")
        self.assertEqual(info["backend"], "st")
        self.assertEqual(info["dim"], 3)
        meta = c._vmeta(self.root)
        self.assertEqual(meta["backend"], "st")
        self.assertEqual(meta["idf"], "")  # dense backend stores no idf
        res = c.semantic_search(self.root, "stripe")
        self.assertIn("Stripe", res[0]["title"])

    def test_st_backend_import_guard(self):
        try:
            import sentence_transformers  # noqa: F401
            self.skipTest("sentence-transformers is installed; guard path not exercised")
        except ImportError:
            with self.assertRaises(SystemExit):
                import ai_cartridge.engine.search as search_mod
                search_mod.get_embedder("st")

    def test_semantic_query_errors_without_index(self):
        with self.assertRaises(SystemExit):
            c.semantic_search(self.root, "anything")

    # ---- resolve -----------------------------------------------------------
    def _make_open_correction(self, title, body):
        p = c.add_memory(self.root, "correction", title, body,
                         extra_meta={"status": "open"}, quiet=True)
        return self._id(p)

    def test_resolve_lists_open_corrections(self):
        self._make_open_correction("Move off Stripe", "switch to Adyen")
        out = io.StringIO()
        with redirect_stdout(out):
            res = c.resolve(self.root)
        self.assertEqual(res["still_open"], 1)
        self.assertIn("open correction", out.getvalue())

    def test_resolve_apply_supersedes_target(self):
        dec = c.add_memory(self.root, "decision", "Use Stripe", "Payments via Stripe.", quiet=True)
        did = self._id(dec)
        cid = self._make_open_correction("Move to Adyen", "switch payments provider")
        res = c.resolve(self.root, correction=cid, target=did)
        self.assertEqual(res["applied"], 1)
        dmeta = c.parse_frontmatter((self.root / c.find_doc_by_id(self.root, did)).read_text(encoding="utf-8"))[0]
        self.assertEqual(dmeta["status"], "superseded")
        self.assertEqual(dmeta["superseded_by"], cid)
        cmeta = c.parse_frontmatter((self.root / c.find_doc_by_id(self.root, cid)).read_text(encoding="utf-8"))[0]
        self.assertEqual(cmeta["status"], "active")

    def test_resolve_dismiss_keeps_standalone(self):
        cid = self._make_open_correction("Random correction", "no target")
        res = c.resolve(self.root, correction=cid, dismiss=True)
        self.assertEqual(res["dismissed"], 1)
        cmeta = c.parse_frontmatter((self.root / c.find_doc_by_id(self.root, cid)).read_text(encoding="utf-8"))[0]
        self.assertEqual(cmeta["status"], "active")
        self.assertEqual(cmeta.get("resolved"), "dismissed")

    def test_resolve_auto_matches_clear_target(self):
        dec = c.add_memory(self.root, "decision", "Use Stripe for payments",
                           "Card payments are processed by Stripe checkout.", quiet=True)
        did = self._id(dec)
        self._make_open_correction("Move payments off Stripe",
                                   "stop using Stripe checkout, adopt Adyen for card payments")
        res = c.resolve(self.root, auto=True)
        self.assertEqual(res["applied"], 1)
        dmeta = c.parse_frontmatter((self.root / c.find_doc_by_id(self.root, did)).read_text(encoding="utf-8"))[0]
        self.assertEqual(dmeta["status"], "superseded")


if __name__ == "__main__":
    unittest.main(verbosity=2)
