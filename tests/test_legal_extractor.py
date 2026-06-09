"""Tests for legal causal extraction pipeline."""
import pytest
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import os


class TestParseJudgmentDate:
    def test_precise_date_from_title(self):
        from llm_kosh.engine.extraction.legal_extractor import parse_judgment_date
        dt = parse_judgment_date(
            "10589-2004-supremecourt-2004-...",
            "10589-2004___supremecourt__2004__Judgement_11-Feb-2020",
        )
        assert dt == datetime(2020, 2, 11, tzinfo=timezone.utc)

    def test_year_from_filename(self):
        from llm_kosh.engine.extraction.legal_extractor import parse_judgment_date
        dt = parse_judgment_date("10589-supremecourt-2004-xyz", "")
        assert dt == datetime(2004, 1, 1, tzinfo=timezone.utc)

    def test_fallback_date(self):
        from llm_kosh.engine.extraction.legal_extractor import parse_judgment_date
        dt = parse_judgment_date("unknown-file.md", "")
        assert dt == datetime(2000, 1, 1, tzinfo=timezone.utc)

    def test_underscore_separator_in_filename(self):
        from llm_kosh.engine.extraction.legal_extractor import parse_judgment_date
        dt = parse_judgment_date("file_supremecourt_1998_abc.md", "")
        assert dt == datetime(1998, 1, 1, tzinfo=timezone.utc)

    def test_precise_date_takes_priority_over_filename_year(self):
        from llm_kosh.engine.extraction.legal_extractor import parse_judgment_date
        dt = parse_judgment_date(
            "file-supremecourt-1990-abc.md",
            "Judgment_05-Mar-2015",
        )
        assert dt == datetime(2015, 3, 5, tzinfo=timezone.utc)


class TestCleanBody:
    def test_strips_table_rows(self):
        from llm_kosh.engine.extraction.legal_extractor import clean_body
        body = "Some text\n| col1 | col2 |\n| --- | --- |\nMore text"
        result = clean_body(body)
        assert "|" not in result
        assert "Some text" in result
        assert "More text" in result

    def test_strips_lone_page_numbers(self):
        from llm_kosh.engine.extraction.legal_extractor import clean_body
        body = "Some text\n4\nMore text"
        result = clean_body(body)
        assert "Some text" in result
        assert "More text" in result
        # The lone '4' should not appear as a standalone token
        tokens = result.split()
        assert "4" not in tokens

    def test_collapses_multiple_spaces(self):
        from llm_kosh.engine.extraction.legal_extractor import clean_body
        body = "word1   word2\n\n\nword3"
        result = clean_body(body)
        assert "  " not in result

    def test_empty_body(self):
        from llm_kosh.engine.extraction.legal_extractor import clean_body
        assert clean_body("") == ""


class TestPatterns:
    def test_cites_scc_pattern(self):
        import re
        from llm_kosh.engine.extraction.patterns import CITES_PATTERNS
        text = "[See Kavita Chandrakant Lakhani v. State of Maharashtra, (2018) 6 SCC 664]"
        matched = any(re.search(p, text, re.IGNORECASE) for p in CITES_PATTERNS)
        assert matched

    def test_cites_supra_pattern(self):
        import re
        from llm_kosh.engine.extraction.patterns import CITES_PATTERNS
        text = "As held in Commissioner of Customs v. KRBL Ltd. (supra)"
        matched = any(re.search(p, text, re.IGNORECASE) for p in CITES_PATTERNS)
        assert matched

    def test_overrules_pattern(self):
        import re
        from llm_kosh.engine.extraction.patterns import OVERRULES_PATTERNS
        text = "The judgment in Commissioner of Customs, Bangalore (supra) being incorrect is therefore overruled."
        matched = any(re.search(p, text, re.IGNORECASE) for p in OVERRULES_PATTERNS)
        assert matched

    def test_overrules_no_longer_good_law(self):
        import re
        from llm_kosh.engine.extraction.patterns import OVERRULES_PATTERNS
        text = "That decision is no longer good law after the Constitution Bench verdict."
        matched = any(re.search(p, text, re.IGNORECASE) for p in OVERRULES_PATTERNS)
        assert matched

    def test_supersedes_repeal(self):
        import re
        from llm_kosh.engine.extraction.patterns import SUPERSEDES_PATTERNS
        text = (
            "The Disabilities Act, 1995 which now stands repealed and is replaced by "
            "the Rights of Persons with Disabilities Act, 2016"
        )
        matched = any(re.search(p, text, re.IGNORECASE) for p in SUPERSEDES_PATTERNS)
        assert matched

    def test_interprets_section(self):
        import re
        from llm_kosh.engine.extraction.patterns import INTERPRETS_PATTERNS
        text = "Section 14 of the Limitation Act provides for exclusion of time."
        matched = any(re.search(p, text, re.IGNORECASE) for p in INTERPRETS_PATTERNS)
        assert matched

    def test_applies_pattern(self):
        import re
        from llm_kosh.engine.extraction.patterns import APPLIES_PATTERNS
        text = "Applying the principle laid down in the earlier judgment, we hold that"
        matched = any(re.search(p, text, re.IGNORECASE) for p in APPLIES_PATTERNS)
        assert matched

    def test_distinguishes_pattern(self):
        import re
        from llm_kosh.engine.extraction.patterns import DISTINGUISHES_PATTERNS
        text = "The facts of the present case are clearly distinguishable from those in the cited authority."
        matched = any(re.search(p, text, re.IGNORECASE) for p in DISTINGUISHES_PATTERNS)
        assert matched

    def test_causes_pattern(self):
        import re
        from llm_kosh.engine.extraction.patterns import CAUSES_PATTERNS
        text = "Aggrieved by the order of the High Court, the appellant filed an appeal before this Court."
        matched = any(re.search(p, text, re.IGNORECASE) for p in CAUSES_PATTERNS)
        assert matched


class TestComputeConfidence:
    def test_reporter_boosts_confidence(self):
        from llm_kosh.engine.extraction.legal_extractor import compute_confidence
        c = compute_confidence(
            0.85,
            "as held in Case v. Other (2018) 6 SCC 664",
            "(2018) 6 SCC 664",
        )
        assert c > 0.85

    def test_quoted_block_lowers_confidence(self):
        from llm_kosh.engine.extraction.legal_extractor import compute_confidence
        c = compute_confidence(0.85, '"the judgment was overruled"', "")
        assert c < 0.85

    def test_floor_at_040(self):
        from llm_kosh.engine.extraction.legal_extractor import compute_confidence
        c = compute_confidence(0.50, '"NON-REPORTABLE (supra)"', "")
        assert c >= 0.40

    def test_cap_at_095(self):
        from llm_kosh.engine.extraction.legal_extractor import compute_confidence
        c = compute_confidence(
            0.95,
            "as held in Case v. Other (2018) 6 SCC 664 AIR 2018",
            "(2018) 6 SCC 664",
        )
        assert c <= 0.95

    def test_supra_without_citation_lowers_confidence(self):
        from llm_kosh.engine.extraction.legal_extractor import compute_confidence
        c = compute_confidence(0.85, "as held in Some Case v. Other (supra)", "")
        assert c < 0.85

    def test_non_reportable_lowers_confidence(self):
        from llm_kosh.engine.extraction.legal_extractor import compute_confidence
        c = compute_confidence(0.85, "NON-REPORTABLE judgment", "")
        assert c < 0.85


class TestParseFrontmatter:
    def test_standard_frontmatter(self, tmp_path):
        from llm_kosh.engine.extraction.legal_extractor import parse_frontmatter
        content = (
            "---\n"
            "id: abc123\n"
            "title: Test v. Other_11-Feb-2020\n"
            "status: active\n"
            "---\n"
            "Body text here."
        )
        f = tmp_path / "test.md"
        f.write_text(content, encoding="utf-8")
        meta = parse_frontmatter(str(f))
        assert meta["id"] == "abc123"
        assert meta["status"] == "active"
        assert "Body text here" in meta["body"]

    def test_no_frontmatter(self, tmp_path):
        from llm_kosh.engine.extraction.legal_extractor import parse_frontmatter
        f = tmp_path / "test.md"
        f.write_text("Just body text.", encoding="utf-8")
        meta = parse_frontmatter(str(f))
        assert meta["body"] == "Just body text."
        assert meta["status"] == "active"
        assert meta["id"] is None

    def test_inactive_status(self, tmp_path):
        from llm_kosh.engine.extraction.legal_extractor import parse_frontmatter
        content = "---\nid: xyz\nstatus: archived\n---\nSome body."
        f = tmp_path / "test.md"
        f.write_text(content, encoding="utf-8")
        meta = parse_frontmatter(str(f))
        assert meta["status"] == "archived"

    def test_missing_status_defaults_to_active(self, tmp_path):
        from llm_kosh.engine.extraction.legal_extractor import parse_frontmatter
        content = "---\nid: nnn\ntitle: A v. B\n---\nBody."
        f = tmp_path / "test.md"
        f.write_text(content, encoding="utf-8")
        meta = parse_frontmatter(str(f))
        assert meta["status"] == "active"


class TestProcessDocumentSmoke:
    def test_process_vernacular_returns_none(self, tmp_path):
        from llm_kosh.engine.extraction.legal_extractor import process_document

        class MockDAG:
            nodes = {}

        class MockEngine:
            dag = MockDAG()

        # Vernacular filename — must return None before opening file
        result = process_document(
            str(tmp_path / "10000-vernacular-2008.md"), MockEngine()
        )
        assert result is None

    def test_process_inactive_document_returns_none(self, tmp_path):
        from llm_kosh.engine.extraction.legal_extractor import process_document

        class MockDAG:
            nodes = {}

        class MockEngine:
            dag = MockDAG()

        content = "---\nid: abc\nstatus: archived\n---\nSome body content here."
        f = tmp_path / "judgment.md"
        f.write_text(content, encoding="utf-8")
        result = process_document(str(f), MockEngine())
        assert result is None

    def test_process_short_body_returns_none(self, tmp_path):
        from llm_kosh.engine.extraction.legal_extractor import process_document

        class MockDAG:
            nodes = {}

        class MockEngine:
            dag = MockDAG()

        content = "---\nid: abc\nstatus: active\n---\nToo short."
        f = tmp_path / "judgment.md"
        f.write_text(content, encoding="utf-8")
        result = process_document(str(f), MockEngine())
        assert result is None


class TestBuildCaseIndex:
    def test_extracts_vs_pattern(self):
        from llm_kosh.engine.extraction.legal_extractor import build_case_index
        from unittest.mock import MagicMock

        fact = MagicMock()
        fact.content = "Rajesh Kumar v. State of Bihar (2010) 3 SCC 100"

        dag = MagicMock()
        dag.nodes = {"fact.abc123": fact}

        index = build_case_index(dag)
        assert any("rajesh kumar" in k for k in index)

    def test_empty_dag(self):
        from llm_kosh.engine.extraction.legal_extractor import build_case_index
        from unittest.mock import MagicMock

        dag = MagicMock()
        dag.nodes = {}
        index = build_case_index(dag)
        assert index == {}


class TestExtractFactsAndEdges:
    def test_returns_list(self):
        from llm_kosh.engine.extraction.legal_extractor import extract_facts_and_edges
        text = "The appeal was filed after the High Court dismissed the petition."
        results = extract_facts_and_edges(text, "test.md", {})
        assert isinstance(results, list)

    def test_max_20_results(self):
        from llm_kosh.engine.extraction.legal_extractor import extract_facts_and_edges
        # Generate text with many matching sentences
        sentence = (
            "Aggrieved by the order, the appellant preferred an appeal before this Court. "
        )
        text = sentence * 30
        results = extract_facts_and_edges(text, "test.md", {})
        assert len(results) <= 20

    def test_result_structure(self):
        from llm_kosh.engine.extraction.legal_extractor import extract_facts_and_edges
        text = (
            "As held in State of Bihar v. Ram Prasad, (2005) 2 SCC 100, the principle applies. "
            "Section 14 of the Act provides for extension of time."
        )
        results = extract_facts_and_edges(text, "test.md", {})
        if results:
            r = results[0]
            assert "content" in r
            assert "pattern_type" in r
            assert "confidence" in r
            assert "edge_type" in r
            assert 0.40 <= r["confidence"] <= 0.95
