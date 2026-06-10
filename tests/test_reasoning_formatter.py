"""Tests for llm_kosh/engine/reasoning/formatter.py"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone, timedelta

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.formatter import format_narrative, _extract_title, _extract_body
from llm_kosh.engine.reasoning.causal_dag import EdgeType


def test_extract_title_strips_hash():
    assert _extract_title("# My Decision\nBody text here.") == "My Decision"


def test_extract_title_max_60():
    long = "A" * 80
    assert len(_extract_title(long)) <= 60


def test_extract_body_first_sentence():
    content = "# Title\nFirst sentence. Second sentence."
    body = _extract_body(content)
    assert "First sentence" in body
    assert "Second sentence" not in body


def test_format_narrative_empty_bundle():
    # Build an engine with no facts
    with TemporaryDirectory() as t:
        root = Path(t)
        init_cartridge(root, "test")
        engine = ReasoningEngine(root)
        result = engine.query("anything", depth=3)
        out = format_narrative(result, "anything")
    assert "No causal chain" in out


def test_format_narrative_with_facts():
    with TemporaryDirectory() as t:
        root = Path(t)
        init_cartridge(root, "test")
        engine = ReasoningEngine(root)
        now = datetime.now(timezone.utc)

        ids = []
        for i, text in enumerate([
            "# Auth migration approved\nOAuth2 migration approved by steering.",
            "# OAuth2 done\nOAuth2 provider integration completed.",
            "# Bug found\nToken refresh bug discovered in production.",
        ]):
            t_ = now + timedelta(days=i)
            fid = engine.ingest(text, t_, t_, t_ + timedelta(days=365), 0.9, [])
            ids.append(fid)

        for i in range(len(ids) - 1):
            engine.dag.add_edge(ids[i], ids[i + 1], EdgeType.ENABLES, 0.9,
                                now + timedelta(days=i), None, "test")

        qt = (now + timedelta(days=5)).timestamp()
        result = engine.query("auth migration", temporal_context=str(qt), depth=5)
        out = format_narrative(result, "auth migration")

    assert "CAUSAL TIMELINE" in out
    assert "stable" in out.lower() or "marginal" in out.lower() or "unstable" in out.lower()
    # At least one fact's content appears
    assert any(word in out for word in ["Auth", "OAuth2", "Bug", "auth", "migration"])


def test_format_narrative_stability_header():
    with TemporaryDirectory() as t:
        root = Path(t)
        init_cartridge(root, "test")
        engine = ReasoningEngine(root)
        now = datetime.now(timezone.utc)
        fid = engine.ingest("Decision: use PostgreSQL for auth.", now, now,
                            now + timedelta(days=365), 0.9, [])
        result = engine.query("PostgreSQL", temporal_context=str((now + timedelta(days=1)).timestamp()))
        out = format_narrative(result, "PostgreSQL")

    assert "stability:" in out.lower()
    assert any(s in out for s in ["STABLE", "MARGINAL", "UNSTABLE"])
