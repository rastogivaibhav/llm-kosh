#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v0.9 — personal workflow polish.
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


class V09Test(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-v09-"))
        self.root = self.dir / "CART"
        c.init_cartridge(self.root, "Test Owner")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _quiet(self, fn, *a, **k):
        with redirect_stdout(io.StringIO()):
            return fn(*a, **k)

    # ---- inbox -------------------------------------------------------------
    def test_inbox_capture_then_list(self):
        res = self._quiet(c.inbox, self.root, capture="Try pgvector for ranking")
        self.assertIn("captured", res)
        listing = self._quiet(c.inbox, self.root)
        self.assertEqual(len(listing["inbox"]), 1)
        self.assertEqual(listing["inbox"][0]["title"], "Try pgvector for ranking")

    def test_inbox_item_has_inbox_status(self):
        self._quiet(c.inbox, self.root, capture="quick idea")
        p = next((self.root / "source" / "notes").glob("*.md"))
        meta = c.parse_frontmatter(p.read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["status"], "inbox")

    # ---- promote -----------------------------------------------------------
    def test_promote_note_to_decision(self):
        res = self._quiet(c.inbox, self.root, capture="Use teacher approval queue")
        nid = res["captured"]
        out = self._quiet(c.promote, self.root, nid, "decision", project="SelectiveOS")
        self.assertEqual(out["to_kind"], "decision")
        # original marked promoted, non-destructive
        orig = c.parse_frontmatter((self.root / c.find_doc_by_id(self.root, nid)).read_text(encoding="utf-8"))[0]
        self.assertEqual(orig["status"], "promoted")
        self.assertEqual(orig["promoted_to"], out["to"])
        # new decision exists and is searchable
        new = c.parse_frontmatter((self.root / c.find_doc_by_id(self.root, out["to"])).read_text(encoding="utf-8"))[0]
        self.assertEqual(new["type"], "decision")
        self.assertEqual(new["project"], "SelectiveOS")
        self.assertEqual(new["promoted_from"], nid)

    def test_promote_missing_id_errors(self):
        with self.assertRaises(SystemExit):
            self._quiet(c.promote, self.root, "nope.0000", "decision")

    # ---- today -------------------------------------------------------------
    def test_today_reports_gaps_and_corrections(self):
        c.add_memory(self.root, "gap", "DPIA needed", "x", extra_meta={"status": "open"}, quiet=True)
        c.add_memory(self.root, "correction", "fix", "y", extra_meta={"status": "open"}, quiet=True)
        self._quiet(c.inbox, self.root, capture="captured thing")
        res = self._quiet(c.today, self.root)
        self.assertIn("DPIA needed", res["open_gaps"])
        self.assertEqual(len(res["open_corrections"]), 1)
        self.assertEqual(res["inbox"], 1)

    # ---- receipt-template --------------------------------------------------
    def test_receipt_template_text(self):
        out = io.StringIO()
        with redirect_stdout(out):
            txt = c.receipt_template(self.root)
        self.assertIn("# MEMORY_RECEIPT", txt)
        self.assertIn("## New decisions", txt)
        self.assertIn("## Corrections", txt)

    # ---- daily-pack --------------------------------------------------------
    def test_daily_pack_creates_uploadable_zip(self):
        c.add_memory(self.root, "project", "SelectiveOS", "prep platform", quiet=True)
        c.add_memory(self.root, "decision", "Teacher approval", "queue", project="SelectiveOS",
                     visibility="shareable", quiet=True)
        out = self.dir / "today.zip"
        self._quiet(c.daily_pack, self.root, out, include_private=True)
        self.assertTrue(out.exists())
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        self.assertIn("01_BOOT.md", names)
        self.assertIn("11_MANIFEST.json", names)

    # ---- static-site -------------------------------------------------------
    def test_static_site_generates_local_files(self):
        c.add_memory(self.root, "project", "SelectiveOS", "prep platform", quiet=True)
        c.add_memory(self.root, "decision", "Teacher approval", "queue body", project="SelectiveOS",
                     visibility="shareable", quiet=True)
        self._quiet(c.static_site, self.root)
        site = self.root / "exports" / "site"
        self.assertTrue((site / "index.html").exists())
        self.assertTrue((site / "style.css").exists())
        self.assertTrue((site / "search.json").exists())
        self.assertTrue(any((site / "projects").glob("*.html")))
        self.assertTrue(any((site / "decisions").glob("*.html")))
        # search.json is valid and lists the decision
        data = json.loads((site / "search.json").read_text(encoding="utf-8"))
        self.assertTrue(any(i["kind"] == "decision" for i in data["items"]))

    def test_static_site_excludes_private_by_default(self):
        c.add_memory(self.root, "decision", "SecretDecision",
                     "PRIVATEBODYXYZ", visibility="private", quiet=True)
        self._quiet(c.static_site, self.root)
        site = self.root / "exports" / "site"
        blob = "".join(p.read_text(encoding="utf-8") for p in site.rglob("*")
                       if p.is_file() and p.suffix in (".html", ".json"))
        self.assertNotIn("PRIVATEBODYXYZ", blob, "private content must not appear in default site")

    def test_static_site_include_private_flag(self):
        c.add_memory(self.root, "decision", "SecretDecision",
                     "PRIVATEBODYXYZ", visibility="private", quiet=True)
        self._quiet(c.static_site, self.root, include_private=True)
        site = self.root / "exports" / "site"
        blob = "".join(p.read_text(encoding="utf-8") for p in site.rglob("*")
                       if p.is_file() and p.suffix in (".html", ".json"))
        self.assertIn("SecretDecision", blob)

    def test_static_site_no_js_framework(self):
        c.add_memory(self.root, "project", "P", "x", visibility="shareable", quiet=True)
        self._quiet(c.static_site, self.root)
        idx = (self.root / "exports" / "site" / "index.html").read_text(encoding="utf-8")
        low = idx.lower()
        for framework in ("react", "vue", "angular", "cdn.", "https://"):
            self.assertNotIn(framework, low, f"site must be framework-free/offline ({framework})")


if __name__ == "__main__":
    unittest.main(verbosity=2)
