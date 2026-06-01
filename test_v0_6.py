#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v0.6 — context pack compiler v2.
Standard library only."""

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import cartridge as c


class V06Test(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-v06-"))
        self.root = self.dir / "CART"
        c.init_cartridge(self.root, "Test Owner")
        # a small but varied corpus
        c.add_memory(self.root, "project", "SelectiveOS", "UK 11+ prep platform.", quiet=True)
        c.add_memory(self.root, "decision", "Teacher approval queue",
                     "AI lessons must be teacher-approved before student-facing.",
                     project="SelectiveOS", quiet=True)
        c.add_memory(self.root, "decision", "Use Stripe", "Card payments via Stripe.",
                     project="SelectiveOS", quiet=True)
        c.add_memory(self.root, "prompt", "Lesson generator prompt",
                     "Generate a teacher-reviewable lesson on a topic.", project="SelectiveOS", quiet=True)
        c.add_memory(self.root, "gap", "DPIA needed", "Need a DPIA for storing student answers.",
                     project="SelectiveOS", extra_meta={"status": "open"}, quiet=True)
        c.add_memory(self.root, "file", "lesson_schema.json", "Schema for lessons.",
                     project="SelectiveOS", quiet=True)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _pack(self, **kw):
        out = self.dir / kw.pop("out", "pack.zip")
        c.pack_context(self.root, kw.pop("query", "SelectiveOS teacher lessons"),
                       kw.pop("target", "chatgpt"), out, include_private=True, **kw)
        return out

    def _names(self, zp):
        with zipfile.ZipFile(zp) as zf:
            return set(zf.namelist())

    def _read(self, zp, name):
        with zipfile.ZipFile(zp) as zf:
            return zf.read(name).decode("utf-8")

    # ---- structure ---------------------------------------------------------
    def test_pack_has_all_required_files(self):
        out = io.StringIO()
        with redirect_stdout(out):
            zp = self._pack()
        names = self._names(zp)
        for req in c.PACK_REQUIRED:
            self.assertIn(req, names, f"pack missing {req}")
        self.assertTrue(any(n.startswith("provider/") for n in names))
        self.assertTrue(any(n.startswith("source-files/") for n in names))

    def test_manifest_has_required_keys(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack()
        man = json.loads(self._read(zp, "11_MANIFEST.json"))
        for k in c.MANIFEST_REQUIRED_KEYS:
            self.assertIn(k, man)
        self.assertEqual(man["schema"], "ai-memory-context-pack.v1")
        self.assertTrue(man["cartridge_id"].startswith("cart_"))

    def test_source_map_links_back_to_source(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack()
        sm = json.loads(self._read(zp, "10_SOURCE_MAP.json"))
        self.assertTrue(sm["matches"])
        for e in sm["matches"]:
            self.assertTrue(e["id"])
            self.assertTrue(e["source_path"].replace("\\", "/").startswith("source/"))

    def test_boot_specifies_read_order(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack()
        boot = self._read(zp, "01_BOOT.md")
        self.assertIn("01_BOOT.md", boot)
        self.assertIn("12_MEMORY_RECEIPT_TEMPLATE.md", boot)

    def test_do_not_assume_lists_open_gap(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack()
        dna = self._read(zp, "09_DO_NOT_ASSUME.md")
        self.assertIn("DPIA", dna)

    # ---- profiles ----------------------------------------------------------
    def test_profile_files_generated(self):
        cases = {"chatgpt": "provider/CHATGPT_CONTEXT.md",
                 "claude": "provider/CLAUDE_CONTEXT.md",
                 "gemini": "provider/GEMINI_CONTEXT.md",
                 "deepseek": "provider/DEEPSEEK_CONTEXT.txt",
                 "codex": "provider/CODEX_CONTEXT.md",
                 "human": "provider/HUMAN_CONTEXT.md"}
        for profile, fname in cases.items():
            with redirect_stdout(io.StringIO()):
                zp = self._pack(target=profile, out=f"{profile}.zip")
            self.assertIn(fname, self._names(zp), f"{profile} missing {fname}")

    def test_human_profile_is_handover(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack(target="human", out="h.zip")
        self.assertIn("Handover", self._read(zp, "provider/HUMAN_CONTEXT.md"))

    def test_codex_profile_emphasises_projects(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack(target="codex", out="cx.zip")
        body = self._read(zp, "provider/CODEX_CONTEXT.md")
        self.assertIn("Projects in scope", body)

    # ---- budget ------------------------------------------------------------
    def test_budget_small_limits_docs(self):
        for i in range(15):
            c.add_memory(self.root, "note", f"note {i}", f"body alpha keyword {i}", quiet=True)
        with redirect_stdout(io.StringIO()):
            zp = self._pack(query="alpha keyword", budget="small", out="small.zip")
        man = json.loads(self._read(zp, "11_MANIFEST.json"))
        self.assertLessEqual(man["docs_selected"], c.BUDGETS["small"][0])

    def test_max_chars_enforced(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack(max_chars=200, out="tiny.zip")
        man = json.loads(self._read(zp, "11_MANIFEST.json"))
        self.assertLessEqual(man["chars_used"], 200 + 100)  # allow truncation marker slack
        self.assertEqual(man["chars_budget"], 200)

    # ---- validate / explain ------------------------------------------------
    def test_validate_pack_passes_on_valid(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack()
            res = c.validate_pack(zp)
        self.assertTrue(res["ok"], res["issues"])

    def test_validate_pack_fails_missing_boot(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack()
        broken = self.dir / "broken.zip"
        with zipfile.ZipFile(zp) as zin, zipfile.ZipFile(broken, "w") as zout:
            for n in zin.namelist():
                if n in ("01_BOOT.md", "11_MANIFEST.json"):
                    continue
                zout.writestr(n, zin.read(n))
        with redirect_stdout(io.StringIO()):
            res = c.validate_pack(broken)
        self.assertFalse(res["ok"])
        self.assertTrue(any("01_BOOT.md" in i for i in res["issues"]))

    def test_explain_pack_runs(self):
        with redirect_stdout(io.StringIO()):
            zp = self._pack()
        out = io.StringIO()
        with redirect_stdout(out):
            c.explain_pack(zp)
        self.assertIn("target profile", out.getvalue())

    # ---- secret gate still strict -----------------------------------------
    def test_pack_blocks_on_secret(self):
        c.add_memory(self.root, "decision", "Creds", "production password: hunter2value",
                     project="SelectiveOS", quiet=True)
        out = self.dir / "leak.zip"
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                c.pack_context(self.root, "Creds password", "chatgpt", out, include_private=True)
        self.assertEqual(ctx.exception.code, 2)
        self.assertFalse(out.exists())

    def test_pack_redacts_clean(self):
        c.add_memory(self.root, "decision", "Creds", "token=ghp_abcdefghijklmnopqrst1234",
                     project="SelectiveOS", quiet=True)
        out = self.dir / "safe.zip"
        with redirect_stdout(io.StringIO()):
            c.pack_context(self.root, "Creds token", "chatgpt", out, include_private=True, redact=True)
        blob = "".join(self._read(out, n) for n in self._names(out)
                       if n.endswith((".md", ".json", ".txt")))
        self.assertNotIn("ghp_abcdefghijklmnopqrst1234", blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)
