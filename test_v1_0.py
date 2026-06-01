#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v1.0 — backup, restore, migration.
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


class V10Test(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-v10-"))
        self.root = self.dir / "CART"
        c.init_cartridge(self.root, "Test Owner")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _quiet(self, fn, *a, **k):
        with redirect_stdout(io.StringIO()):
            return fn(*a, **k)

    # ---- export-backup -----------------------------------------------------
    def test_export_backup_contains_source_not_index(self):
        c.add_memory(self.root, "decision", "Keep this", "important body", quiet=True)
        out = self.dir / "bk.zip"
        self._quiet(c.export_backup, self.root, out)
        self.assertTrue(out.exists())
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        self.assertIn("BACKUP_MANIFEST.json", names)
        self.assertIn("CARTRIDGE.json", names)
        self.assertTrue(any(n.startswith("source/") for n in names))
        self.assertTrue(any(n.startswith("ledger/") for n in names))
        # derived indexes are NOT in the backup
        self.assertFalse(any("memory.sqlite" in n for n in names))
        self.assertFalse(any("vectors.sqlite" in n for n in names))

    # ---- round-trip --------------------------------------------------------
    def test_backup_restore_roundtrip(self):
        c.add_memory(self.root, "decision", "Teacher approval", "queue body", project="P", quiet=True)
        c.add_memory(self.root, "gap", "DPIA", "needed", extra_meta={"status": "open"}, quiet=True)
        out = self.dir / "bk.zip"
        self._quiet(c.export_backup, self.root, out)

        restored = self.dir / "RESTORED"
        res = self._quiet(c.import_backup, restored, out)
        self.assertGreater(res["restored"], 0)
        # query works against the rebuilt index
        hits = c.query_memory(restored, "teacher approval queue")
        self.assertTrue(any(h["title"] == "Teacher approval" for h in hits))
        # same cartridge_id preserved
        self.assertEqual(c.cartridge_meta(restored)["cartridge_id"],
                         c.cartridge_meta(self.root)["cartridge_id"])

    def test_import_refuses_nonempty_without_force(self):
        c.add_memory(self.root, "note", "a", "x", quiet=True)
        out = self.dir / "bk.zip"
        self._quiet(c.export_backup, self.root, out)
        # target already has memories
        target = self.dir / "T"
        c.init_cartridge(target, "Other")
        c.add_memory(target, "note", "existing", "keepme", quiet=True)
        with self.assertRaises(SystemExit):
            self._quiet(c.import_backup, target, out)

    def test_import_force_overwrites(self):
        c.add_memory(self.root, "note", "frombackup", "BACKUPBODY", quiet=True)
        out = self.dir / "bk.zip"
        self._quiet(c.export_backup, self.root, out)
        target = self.dir / "T"
        c.init_cartridge(target, "Other")
        c.add_memory(target, "note", "existing", "x", quiet=True)
        res = self._quiet(c.import_backup, target, out, force=True)
        self.assertGreater(res["restored"], 0)
        hits = c.query_memory(target, "frombackup")
        self.assertTrue(any(h["title"] == "frombackup" for h in hits))

    def test_import_rejects_non_backup_zip(self):
        bogus = self.dir / "bogus.zip"
        with zipfile.ZipFile(bogus, "w") as zf:
            zf.writestr("hello.txt", "not a backup")
        with self.assertRaises(SystemExit):
            self._quiet(c.import_backup, self.dir / "X", bogus)

    # ---- migrate -----------------------------------------------------------
    def test_migrate_stamps_version(self):
        # simulate an older cartridge
        cfg = json.loads((self.root / "CARTRIDGE.json").read_text())
        cfg["version"] = "0.5.0"
        cfg.pop("cartridge_id", None)
        (self.root / "CARTRIDGE.json").write_text(json.dumps(cfg))
        res = self._quiet(c.migrate, self.root)
        self.assertTrue(res["migrated"])
        new = json.loads((self.root / "CARTRIDGE.json").read_text())
        self.assertEqual(new["version"], c.APP_VERSION)
        self.assertTrue(new.get("cartridge_id"))
        self.assertTrue(new.get("migrated_from"))

    def test_migrate_dry_run_changes_nothing(self):
        cfg = json.loads((self.root / "CARTRIDGE.json").read_text())
        cfg["version"] = "0.5.0"
        (self.root / "CARTRIDGE.json").write_text(json.dumps(cfg))
        res = self._quiet(c.migrate, self.root, dry_run=True)
        self.assertFalse(res["migrated"])
        self.assertEqual(json.loads((self.root / "CARTRIDGE.json").read_text())["version"], "0.5.0")

    def test_migrate_noop_when_current(self):
        res = self._quiet(c.migrate, self.root)
        self.assertFalse(res["migrated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
