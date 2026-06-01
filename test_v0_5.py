#!/usr/bin/env python3
"""Tests for AI Memory Cartridge v0.5 — conversation importers.
Standard library only. Fixtures are tiny synthetic exports built in setUp
(no real user data)."""

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import cartridge as c


class V05Test(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cart-v05-"))
        self.root = self.dir / "CART"
        self.fx = self.dir / "fixtures"
        self.fx.mkdir()
        c.init_cartridge(self.root, "Test Owner")
        self._build_fixtures()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _build_fixtures(self):
        chatgpt = [{
            "title": "SelectiveOS teacher approval", "create_time": 1714000000.0,
            "mapping": {
                "root": {"id": "root", "parent": None, "children": ["a"], "message": None},
                "a": {"id": "a", "parent": "root", "children": ["b"],
                      "message": {"author": {"role": "user"}, "create_time": 1714000001.0,
                                  "content": {"content_type": "text",
                                              "parts": ["Should AI lessons need teacher approval?"]}}},
                "b": {"id": "b", "parent": "a", "children": [],
                      "message": {"author": {"role": "assistant"}, "create_time": 1714000002.0,
                                  "content": {"content_type": "text",
                                              "parts": ["Yes, route them through a teacher approval queue."]}}},
            }}]
        with zipfile.ZipFile(self.fx / "chatgpt_export.zip", "w") as zf:
            zf.writestr("conversations.json", json.dumps(chatgpt))

        (self.fx / "claude_export.json").write_text(json.dumps([{
            "uuid": "c1", "name": "Pricing chat", "created_at": "2024-05-01T10:00:00Z",
            "chat_messages": [
                {"sender": "human", "text": "Which payment provider?"},
                {"sender": "assistant", "content": [{"type": "text", "text": "Use Stripe for UK checkout."}]},
            ]}]))

        (self.fx / "gemini_activity.json").write_text(json.dumps([
            {"header": "Gemini Apps", "title": "Prompted Explain psychometric scoring",
             "time": "2024-06-02T08:30:00Z"},
            {"header": "Search", "title": "weather reading", "time": "2024-06-02T09:00:00Z"},
        ]))

        (self.fx / "sample_conversation.md").write_text(
            "# Lesson workflow\n\nUser: Do AI lessons need teacher approval?\n"
            "Assistant: Yes, a teacher approval queue gates student-facing lessons.\n")

        (self.fx / "sample_messages.json").write_text(json.dumps(
            [{"role": "user", "text": "hello"}, {"role": "assistant", "text": "hi there"}]))

        (self.fx / "malformed_export.json").write_text("{ not valid json ")

    def _convs(self):
        return list((self.root / "source" / "conversations").glob("*.md"))

    # ---- ChatGPT -----------------------------------------------------------
    def test_import_chatgpt_dry_run_writes_nothing(self):
        out = io.StringIO()
        with redirect_stdout(out):
            summary = c.import_conversations(self.root, "chatgpt",
                                             self.fx / "chatgpt_export.zip", dry_run=True)
        self.assertTrue(summary["dry_run"])
        self.assertEqual(len(summary["conversations"]), 1)
        self.assertEqual(self._convs(), [], "dry-run must not create source records")
        self.assertEqual(list((self.root / "attachments" / "imports").glob("*")), [],
                         "dry-run must not preserve raw")
        self.assertIn("would import", out.getvalue())

    def test_import_chatgpt_real(self):
        summary = c.import_conversations(self.root, "chatgpt", self.fx / "chatgpt_export.zip",
                                         project="SelectiveOS")
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(len(self._convs()), 1)
        meta = c.parse_frontmatter(self._convs()[0].read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["provider"], "chatgpt")
        self.assertEqual(meta["project"], "SelectiveOS")
        self.assertEqual(meta["message_count"], "2")
        self.assertTrue(meta["import_id"].startswith("imp_"))
        self.assertTrue(meta["source_hash"].startswith("sha256:"))
        self.assertTrue(meta.get("conversation_date"))
        # raw preserved and not mutated
        raw = list((self.root / "attachments" / "imports").rglob("*.zip"))
        self.assertEqual(len(raw), 1)
        # searchable
        res = c.query_memory(self.root, "teacher approval")
        self.assertTrue(any(r["kind"] == "conversation" for r in res))

    def test_import_writes_report_and_ledger(self):
        summary = c.import_conversations(self.root, "chatgpt", self.fx / "chatgpt_export.zip")
        self.assertTrue((self.root / summary["report"]).exists())
        events = [json.loads(l) for l in (self.root / "ledger" / "events.jsonl").read_text().splitlines()]
        kinds = [e["event"] for e in events]
        self.assertIn("import.started", kinds)
        self.assertIn("import.completed", kinds)

    # ---- Claude / Gemini ---------------------------------------------------
    def test_import_claude(self):
        c.import_conversations(self.root, "claude", self.fx / "claude_export.json")
        metas = [c.parse_frontmatter(p.read_text(encoding="utf-8"))[0] for p in self._convs()]
        self.assertEqual(len(metas), 1)
        self.assertEqual(metas[0]["provider"], "claude")
        self.assertEqual(metas[0]["conversation_title"], "Pricing chat")
        self.assertTrue(any("Stripe" in p.read_text(encoding="utf-8") for p in self._convs()))

    def test_import_gemini(self):
        c.import_conversations(self.root, "gemini", self.fx / "gemini_activity.json")
        # only the Gemini-headed record is imported (the Search record is filtered)
        self.assertEqual(len(self._convs()), 1)
        meta = c.parse_frontmatter(self._convs()[0].read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["provider"], "gemini")

    # ---- generic -----------------------------------------------------------
    def test_import_generic_markdown(self):
        c.import_conversations(self.root, "generic", self.fx / "sample_conversation.md")
        self.assertEqual(len(self._convs()), 1)
        res = c.query_memory(self.root, "teacher approval")
        self.assertTrue(res)

    def test_import_generic_json_messages(self):
        c.import_conversations(self.root, "generic", self.fx / "sample_messages.json")
        self.assertEqual(len(self._convs()), 1)
        body = self._convs()[0].read_text(encoding="utf-8")
        self.assertIn("hi there", body)

    # ---- options -----------------------------------------------------------
    def test_limit_and_visibility(self):
        # two conversations in one chatgpt file
        data = []
        for i in range(2):
            data.append({"title": f"Chat {i}", "create_time": 1714000000.0 + i,
                         "mapping": {"r": {"parent": None, "children": ["m"], "message": None},
                                     "m": {"parent": "r", "children": [],
                                           "message": {"author": {"role": "user"},
                                                       "content": {"parts": [f"hello {i}"]}}}}})
        f = self.fx / "multi.json"
        f.write_text(json.dumps(data))
        summary = c.import_conversations(self.root, "chatgpt", f, limit=1, visibility="work-safe")
        self.assertEqual(len(summary["conversations"]), 1)
        meta = c.parse_frontmatter(self._convs()[0].read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["visibility"], "work-safe")

    # ---- graceful failure --------------------------------------------------
    def test_malformed_export_does_not_crash(self):
        out = io.StringIO()
        with redirect_stdout(out):
            summary = c.import_conversations(self.root, "chatgpt", self.fx / "malformed_export.json")
        self.assertEqual(self._convs(), [], "nothing imported from malformed file")
        self.assertIn(summary["status"], ("no_conversations", "empty"))
        self.assertTrue((self.root / summary["report"]).exists(), "report written even on failure")
        self.assertTrue(any("not valid JSON" in n or "recognise" in n for n in summary["notes"]))

    def test_unknown_structure_reports_cleanly(self):
        f = self.fx / "weird.json"
        f.write_text(json.dumps({"unexpected": "shape", "no": "conversations"}))
        summary = c.import_conversations(self.root, "claude", f)
        self.assertEqual(summary["status"], "no_conversations")
        self.assertEqual(self._convs(), [])

    # ---- import-report command --------------------------------------------
    def test_import_report_command(self):
        c.import_conversations(self.root, "chatgpt", self.fx / "chatgpt_export.zip")
        out = io.StringIO()
        with redirect_stdout(out):
            c.import_report(self.root)
        text = out.getvalue()
        self.assertIn("Import Report", text)
        self.assertIn("chatgpt", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
