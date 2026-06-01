#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v0.8 — self-healing v2.
Standard library only."""

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import cartridge as c


class V08Test(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-v08-"))
        self.root = self.dir / "CART"
        c.init_cartridge(self.root, "Test Owner")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _quiet(self, fn, *a, **k):
        with redirect_stdout(io.StringIO()):
            return fn(*a, **k)

    def _types(self, report):
        return {i["type"] for i in report["issues"]}

    # ---- audit findings ----------------------------------------------------
    def test_audit_clean_cartridge(self):
        c.add_memory(self.root, "decision", "A", "body", quiet=True)
        report = self._quiet(c.audit, self.root)
        self.assertNotIn("duplicate_id", self._types(report))

    def test_audit_missing_frontmatter(self):
        (self.root / "source" / "notes" / "raw.md").write_text("no frontmatter here", encoding="utf-8")
        report = self._quiet(c.audit, self.root)
        self.assertIn("missing_frontmatter_or_id", self._types(report))

    def test_audit_duplicate_id(self):
        p1 = c.add_memory(self.root, "note", "one", "x", quiet=True)
        did = c.parse_frontmatter(p1.read_text(encoding="utf-8"))[0]["id"]
        p2 = c.add_memory(self.root, "note", "two", "y", quiet=True)
        c.update_doc_meta(self.root, str(p2.relative_to(self.root)), {"id": did})
        report = self._quiet(c.audit, self.root)
        self.assertIn("duplicate_id", self._types(report))

    def test_audit_duplicate_title(self):
        c.add_memory(self.root, "note", "Same Title", "a", quiet=True)
        c.add_memory(self.root, "note", "Same Title", "b", quiet=True)
        report = self._quiet(c.audit, self.root)
        self.assertIn("duplicate_title", self._types(report))

    def test_audit_secret_in_shareable(self):
        c.add_memory(self.root, "note", "leak", "api key: sk_live_abcdef0123456789",
                     visibility="shareable", quiet=True)
        report = self._quiet(c.audit, self.root)
        self.assertIn("secret_in_shareable", self._types(report))

    def test_audit_dangling_superseded_by(self):
        p = c.add_memory(self.root, "decision", "x", "y", quiet=True)
        c.update_doc_meta(self.root, str(p.relative_to(self.root)),
                          {"superseded_by": "missing.id.0000", "status": "superseded"})
        report = self._quiet(c.audit, self.root)
        self.assertIn("dangling_superseded_by", self._types(report))

    def test_audit_superseded_still_exportable(self):
        p = c.add_memory(self.root, "decision", "x", "y", visibility="shareable", quiet=True)
        c.update_doc_meta(self.root, str(p.relative_to(self.root)), {"status": "superseded"})
        report = self._quiet(c.audit, self.root)
        self.assertIn("superseded_still_exportable", self._types(report))

    def test_audit_open_correction(self):
        c.add_memory(self.root, "correction", "fix", "body", extra_meta={"status": "open"}, quiet=True)
        report = self._quiet(c.audit, self.root)
        self.assertIn("open_correction", self._types(report))

    def test_audit_missing_boot(self):
        (self.root / "BOOT.md").unlink()
        report = self._quiet(c.audit, self.root)
        self.assertIn("missing_boot", self._types(report))

    def test_audit_stale_fts_index(self):
        c.add_memory(self.root, "note", "a", "x", quiet=True)
        # tamper the index state so it no longer matches the corpus
        sp = self.root / "indexes" / "index_state.json"
        c.write_json(sp, {"fingerprint": "stale"})
        self.assertTrue(c.index_is_stale(self.root))

    def test_audit_vector_index_out_of_date(self):
        c.add_memory(self.root, "note", "a", "x", quiet=True)
        self._quiet(c.build_vector_index, self.root, "tfidf")
        c.add_memory(self.root, "note", "b", "y", quiet=True)  # corpus grew, vectors stale
        self.assertTrue(c.vector_index_stale(self.root))

    def test_audit_generated_file_without_source(self):
        c.add_memory(self.root, "file", "orphan.json", "contents", quiet=True)
        report = self._quiet(c.audit, self.root)
        self.assertIn("generated_file_without_source", self._types(report))

    # ---- verify-ledger -----------------------------------------------------
    def test_verify_ledger_detects_corrupt_row(self):
        led = self.root / "ledger" / "events.jsonl"
        with led.open("a", encoding="utf-8") as f:
            f.write("this is not json\n")
        res = self._quiet(c.verify_ledger, self.root)
        self.assertEqual(res["bad_rows"], 1)

    def test_audit_flags_corrupt_ledger(self):
        led = self.root / "ledger" / "events.jsonl"
        with led.open("a", encoding="utf-8") as f:
            f.write("{bad\n")
        report = self._quiet(c.audit, self.root)
        self.assertIn("corrupt_ledger_rows", self._types(report))

    # ---- heal modes --------------------------------------------------------
    def test_heal_dry_run_changes_nothing(self):
        (self.root / "source" / "notes" / "orphan.md").write_text(
            "---\ntitle: Orphan\n---\n\n# Orphan\n\nbody\n", encoding="utf-8")
        res = self._quiet(c.heal_safe, self.root, dry_run=True)
        self.assertFalse(res["applied"])
        meta = c.parse_frontmatter((self.root / "source" / "notes" / "orphan.md").read_text(encoding="utf-8"))[0]
        self.assertFalse(meta.get("id"), "dry-run must not write")

    def test_heal_safe_fixes_missing_boot_and_id(self):
        (self.root / "BOOT.md").unlink()
        (self.root / "source" / "notes" / "orphan.md").write_text(
            "---\ntitle: Orphan\n---\n\n# Orphan\n\nbody\n", encoding="utf-8")
        self._quiet(c.heal_safe, self.root)
        self.assertTrue((self.root / "BOOT.md").exists(), "heal regenerates BOOT.md")
        meta = c.parse_frontmatter((self.root / "source" / "notes" / "orphan.md").read_text(encoding="utf-8"))[0]
        self.assertTrue(meta.get("id"))

    def test_heal_does_not_delete_anything(self):
        before = {p.name for p in (self.root / "source").rglob("*.md")}
        p = c.add_memory(self.root, "note", "keep", "body", quiet=True)
        c.update_doc_meta(self.root, str(p.relative_to(self.root)),
                          {"superseded_by": "missing.id", "status": "superseded"})
        self._quiet(c.heal_safe, self.root)
        after = {pp.name for pp in (self.root / "source").rglob("*.md")}
        self.assertTrue(before.issubset(after) or p.name in after)
        self.assertTrue(p.exists(), "heal must never delete source files")

    # ---- repair plan write / apply ----------------------------------------
    def test_write_plan_then_apply_plan(self):
        (self.root / "source" / "notes" / "orphan.md").write_text(
            "---\ntitle: Orphan\n---\n\n# Orphan\n\nbody\n", encoding="utf-8")
        # write plan (no changes)
        self._quiet(c.heal_safe, self.root, write_plan=True)
        plan = self.root / "reports" / "REPAIR_PLAN.json"
        self.assertTrue(plan.exists())
        meta0 = c.parse_frontmatter((self.root / "source" / "notes" / "orphan.md").read_text(encoding="utf-8"))[0]
        self.assertFalse(meta0.get("id"), "write-plan must not change anything")
        # apply plan
        self._quiet(c.heal_safe, self.root, apply_plan=plan)
        meta1 = c.parse_frontmatter((self.root / "source" / "notes" / "orphan.md").read_text(encoding="utf-8"))[0]
        self.assertTrue(meta1.get("id"), "apply-plan should fix the planned item")

    def test_repair_plan_is_human_readable(self):
        c.add_memory(self.root, "note", "leak", "api key: sk_live_abcdef0123456789",
                     visibility="shareable", quiet=True)
        self._quiet(c.write_repair_plan, self.root)
        md = (self.root / "reports" / "REPAIR_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("Repair Plan", md)
        self.assertIn("Manual", md)

    # ---- memory map --------------------------------------------------------
    def test_memory_map_sections(self):
        c.add_memory(self.root, "project", "SelectiveOS", "x", quiet=True)
        c.add_memory(self.root, "decision", "Teacher approval", "y", project="SelectiveOS", quiet=True)
        c.add_memory(self.root, "gap", "DPIA", "z", extra_meta={"status": "open"}, quiet=True)
        self._quiet(c.memory_map, self.root)
        md = (self.root / "MEMORY_MAP.md").read_text(encoding="utf-8")
        for section in ("## Projects", "## Active decisions", "## Open gaps",
                        "## Export packs", "## Index health"):
            self.assertIn(section, md)
        self.assertIn("Teacher approval", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
