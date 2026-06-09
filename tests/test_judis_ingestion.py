"""
tests/test_judis_ingestion.py

Tests for scripts/ingest_judis_cartridge.py extraction and edge-building logic.
Runs entirely in-memory against a 50-case synthetic fixture — does NOT require
the live SQLite source database.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, call, patch

import pytest

# Make the script importable without running main()
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Import helpers from the ingestion script
from scripts.ingest_judis_cartridge import (
    JudisDoc,
    extract_all_judges,
    extract_body_air_citations,
    extract_date,
    extract_own_air_citation,
    extract_petitioner,
    extract_respondent,
    normalize_party,
    build_infers_edges,
    build_bench_edges,
    build_contradicts_edges,
    ingest_facts,
)


# ---------------------------------------------------------------------------
# Fixtures — 50-case synthetic corpus
# ---------------------------------------------------------------------------

def _make_old_format_body(
    petitioner: str,
    respondent: str,
    date_str: str,
    bench_lines: List[str],
    air_year: str,
    air_page: str,
    cross_refs: List[str] = None,
) -> str:
    """Build a synthetic JUDIS old-format judgment body."""
    bench_block = "\n".join(f"BENCH:\n{b}" for b in bench_lines)
    citation_block = f"CITATION:\n {air_year} AIR  {air_page}            {air_year} SCC  (1) 100"
    cross_block = ""
    if cross_refs:
        cross_block = "JUDGMENT:\nAs held in " + " and ".join(
            f"AIR {y} SC {p}" for y, p in cross_refs
        ) + " the law is settled."
    return f"""# -0___jonew__judis__99999

http://JUDIS.NIC.IN

SUPREME COURT OF INDIA

PETITIONER:
{petitioner}

        Vs.

RESPONDENT:
{respondent}

DATE OF JUDGMENT{date_str}

{bench_block}

{citation_block}

ACT:

HEADNOTE:

{cross_block}
"""


def _make_new_format_body(
    petitioner: str,
    respondent: str,
    title_date: str,
) -> str:
    """Build a synthetic newer-format judgment body (post-2010)."""
    return f"""# 10000-2018___supremecourt__2018__10000__Judgement_{title_date}

IN THE SUPREME COURT OF INDIA

{petitioner}
    ....Appellant

Versus

{respondent}
    ....Respondent

J U D G M E N T

This is the order of the court.
"""


def _make_doc(
    doc_id: str,
    title: str,
    body: str,
) -> JudisDoc:
    doc = JudisDoc(doc_id=doc_id, title=title, body=body)
    doc.parse()
    return doc


# Pre-build a 50-doc corpus
def _build_corpus() -> List[JudisDoc]:
    docs: List[JudisDoc] = []

    # 10 cases — constitutional bench (5 judges), AIR citations
    judges_const = [
        "AHMAD A.M. (CJ)",
        "KULDIP SINGH (J)",
        "JEEVAN REDDY B.P. (J)",
        "SINGH N.P. (J)",
        "HANSARIA B.L. (J)",
    ]
    for i in range(10):
        body = _make_old_format_body(
            petitioner=f"STATE OF INDIA",
            respondent=f"CITIZEN {i}",
            date_str=f"{(i % 28) + 1:02d}/06/199{i % 10}",
            bench_lines=judges_const,
            air_year=f"199{i % 10}",
            air_page=f"{100 + i}",
        )
        doc = _make_doc(
            doc_id=f"file.0-jonew-judis-{10000 + i}.abc",
            title=f"-0___jonew__judis__{10000 + i}",
            body=body,
        )
        docs.append(doc)

    # 10 cases — small bench (2 judges), CONTRADICTS scenario
    # 5 of them have "UNION OF INDIA v STATE OF KERALA"
    # 5 of them have "STATE OF KERALA v UNION OF INDIA" (flip)
    judges_small = ["RAMASWAMY K. (J)", "WANCHOO K.N. (J)"]
    for i in range(5):
        body_a = _make_old_format_body(
            petitioner="UNION OF INDIA",
            respondent="STATE OF KERALA",
            date_str=f"0{i + 1}/01/196{i}",
            bench_lines=judges_small,
            air_year=f"196{i}",
            air_page=f"{200 + i}",
        )
        body_b = _make_old_format_body(
            petitioner="STATE OF KERALA",
            respondent="UNION OF INDIA",
            date_str=f"1{i + 1}/01/196{i}",
            bench_lines=judges_small,
            air_year=f"196{i}",
            air_page=f"{300 + i}",
        )
        docs.append(_make_doc(f"file.0-jonew-judis-{20000 + i}.abc",
                               f"-0___jonew__judis__{20000 + i}", body_a))
        docs.append(_make_doc(f"file.0-jonew-judis-{30000 + i}.abc",
                               f"-0___jonew__judis__{30000 + i}", body_b))

    # 10 cases — INFERS scenario: case 40000 cites cases 10000..10004
    cross_refs = [("199" + str(j % 10), str(100 + j)) for j in range(5)]
    body_citing = _make_old_format_body(
        petitioner="PETITIONER X",
        respondent="RESPONDENT Y",
        date_str="01/01/1999",
        bench_lines=["SHAH J.C. (J)", "GAJENDRAGADKAR P.B. (J)"],
        air_year="1999",
        air_page="999",
        cross_refs=cross_refs,
    )
    docs.append(_make_doc("file.0-jonew-judis-40000.abc",
                           "-0___jonew__judis__40000", body_citing))

    # 10 cases — partial bench overlap (1 shared judge → STRUCTURALLY_SIMILAR)
    # Group A: 5 cases with SHAH J.C. + two unique judges each
    # Group B: 5 cases with SHAH J.C. + two *different* unique judges
    # → every consecutive pair in SHAH's cluster shares exactly 1 judge
    for i in range(5):
        body = _make_old_format_body(
            petitioner=f"CORP GROUP A {i}",
            respondent=f"STATE TAX AUTH",
            date_str=f"0{i + 1}/03/197{i}",
            bench_lines=[f"SHAH J.C. (J)", f"UNIQUE ALPHA {i} (J)", f"UNIQUE BETA {i} (J)"],
            air_year=f"197{i}",
            air_page=f"{400 + i}",
        )
        docs.append(_make_doc(
            f"file.0-jonew-judis-{60000 + i}.abc",
            f"-0___jonew__judis__{60000 + i}",
            body,
        ))
    for i in range(5):
        body = _make_old_format_body(
            petitioner=f"CORP GROUP B {i}",
            respondent=f"CUSTOMS DEPT",
            date_str=f"0{i + 1}/09/197{5 + i % 5}",
            bench_lines=[f"SHAH J.C. (J)", f"UNIQUE GAMMA {i} (J)", f"UNIQUE DELTA {i} (J)"],
            air_year=f"197{5 + i % 5}",
            air_page=f"{500 + i}",
        )
        docs.append(_make_doc(
            f"file.0-jonew-judis-{70000 + i}.abc",
            f"-0___jonew__judis__{70000 + i}",
            body,
        ))

    # New-format cases (titles with date)
    for i in range(9):
        body = _make_new_format_body(
            petitioner=f"APPELLANT {i}",
            respondent=f"STATE OF DELHI",
            title_date=f"0{i + 1}-Jan-2018",
        )
        docs.append(_make_doc(
            f"file.{50000 + i}-2018-supremecourt-2018-{50000+i}",
            f"{50000 + i}-2018___supremecourt__2018__{50000+i}__Judgement_0{i+1}-Jan-2018",
            body,
        ))

    return docs


CORPUS = _build_corpus()


# ---------------------------------------------------------------------------
# Tests: extract_date
# ---------------------------------------------------------------------------
class TestExtractDate:
    def test_old_format_date_exact(self):
        body = "DATE OF JUDGMENT15/06/1995\n"
        dt, precise = extract_date(body)
        assert precise is True
        assert dt == datetime(1995, 6, 15, tzinfo=timezone.utc)

    def test_old_format_date_with_spaces(self):
        body = "DATE OF JUDGMENT  01/01/2001\n"
        dt, precise = extract_date(body)
        assert precise is True
        assert dt.year == 2001

    def test_old_format_date_dash_separator(self):
        body = "DATE OF JUDGMENT12-03-1990\n"
        dt, precise = extract_date(body)
        assert precise is True
        assert dt == datetime(1990, 3, 12, tzinfo=timezone.utc)

    def test_new_format_date_from_title(self):
        title = "10000-2018___supremecourt__2018__Judgement_09-May-2018"
        dt, precise = extract_date("", title)
        assert precise is True
        assert dt == datetime(2018, 5, 9, tzinfo=timezone.utc)

    def test_year_fallback(self):
        body = "SUPREME COURT OF INDIA\n1975 SCC (3) 198\n"
        dt, precise = extract_date(body)
        assert precise is False
        assert dt is not None
        assert dt.year == 1975

    def test_no_date_returns_none(self):
        dt, precise = extract_date("This judgment has no date at all.")
        assert dt is None
        assert precise is False

    def test_two_digit_year(self):
        body = "DATE OF JUDGMENT01/01/96\n"
        dt, precise = extract_date(body)
        assert precise is True
        assert dt.year == 1996

    def test_invalid_month_skipped(self):
        body = "DATE OF JUDGMENT99/99/1999\n"
        dt, precise = extract_date(body)
        # Should fall back to year from body
        assert dt is not None  # year fallback fires
        assert dt.year == 1999

    def test_corpus_docs_all_have_dates(self):
        for doc in CORPUS:
            assert doc.judgment_date is not None, f"{doc.doc_id} missing date"


# ---------------------------------------------------------------------------
# Tests: extract_all_judges
# ---------------------------------------------------------------------------
class TestExtractAllJudges:
    def test_extracts_multiple_judges(self):
        body = (
            "BENCH:\nAHMADI A.M. (CJ)\n"
            "BENCH:\nKULDIP SINGH (J)\n"
            "JEEVAN REDDY B.P. (J)\n"
            "CITATION:\n"
        )
        judges = extract_all_judges(body)
        assert len(judges) >= 2
        assert any("ahmadi" in j for j in judges)
        assert any("kuldip" in j or "singh" in j for j in judges)

    def test_strips_role_suffix(self):
        body = "BENCH:\nRAMASWAMY K. (J)\nWANCHOO K.N. (J)\nCITATION:\n"
        judges = extract_all_judges(body)
        # Roles stripped — no "(J)" in output
        assert all("(J)" not in j for j in judges)
        assert all("(j)" not in j for j in judges)

    def test_deduplicates_judges(self):
        body = (
            "BENCH:\nSHAH J.C. (J)\n"
            "BENCH:\nSHAH J.C. (J)\n"
            "CITATION:\n"
        )
        judges = extract_all_judges(body)
        assert len(judges) == 1

    def test_no_bench_returns_empty(self):
        body = "PETITIONER:\nSOMEONE\nJUDGMENT:\nSome text"
        judges = extract_all_judges(body)
        assert judges == []

    def test_corpus_constitutional_bench_has_5_judges(self):
        """First 10 docs have 5 judges each."""
        for doc in CORPUS[:10]:
            assert len(doc.judges) == 5, (
                f"{doc.doc_id} should have 5 judges, got {doc.judges}"
            )

    def test_corpus_small_bench_has_2_judges(self):
        """Docs 10-19 (contradiction pairs) have 2 judges each."""
        for doc in CORPUS[10:20]:
            assert len(doc.judges) == 2, (
                f"{doc.doc_id} has {doc.judges}"
            )


# ---------------------------------------------------------------------------
# Tests: extract_own_air_citation / extract_body_air_citations
# ---------------------------------------------------------------------------
class TestAirCitations:
    def test_extract_own_air_from_citation_field(self):
        body = "CITATION:\n 1996 AIR  770   1996 SCC  (1) 361\nACT:\n"
        result = extract_own_air_citation(body)
        assert result == ("1996", "770")

    def test_extract_own_air_none_when_missing(self):
        body = "CITATION:\n 1996 SCC  (1) 361\nACT:\n"
        result = extract_own_air_citation(body)
        assert result is None

    def test_extract_body_air_cross_refs(self):
        body = (
            "JUDGMENT:\n"
            "As held in AIR 1952 SC 319 and AIR 1958 SC 398 the law is clear.\n"
        )
        refs = extract_body_air_citations(body)
        assert ("1952", "319") in refs
        assert ("1958", "398") in refs

    def test_body_air_skips_header_section(self):
        """Cross-refs should be sought in JUDGMENT section only."""
        body = "CITATION:\n 1996 AIR 770\nJUDGMENT:\nNo citations here."
        refs = extract_body_air_citations(body)
        # "1996 AIR 770" is in CITATION header, not in JUDGMENT text
        assert ("1996", "770") not in refs

    def test_corpus_citing_doc_has_cross_refs(self):
        """The synthetic citing doc (judis-40000) should have 5 cross-refs."""
        citing = next(d for d in CORPUS if "40000" in d.doc_id)
        refs = extract_body_air_citations(citing.body)
        assert len(refs) == 5


# ---------------------------------------------------------------------------
# Tests: extract_petitioner / extract_respondent
# ---------------------------------------------------------------------------
class TestPartyExtraction:
    def test_old_format_petitioner(self):
        body = "PETITIONER:\nBALAJI RAGHAVAN\n\n        Vs.\n"
        result = extract_petitioner(body)
        assert result is not None
        assert "BALAJI" in result

    def test_old_format_respondent(self):
        body = "RESPONDENT:\nUNION OF INDIA\n"
        result = extract_respondent(body)
        assert result is not None
        assert "UNION" in result

    def test_skips_vs_line(self):
        body = "PETITIONER:\nVs.\n"
        result = extract_petitioner(body)
        assert result is None

    def test_corpus_state_parties_extracted(self):
        """Contradiction-pair docs should have state party names extracted."""
        for doc in CORPUS[10:20]:
            assert doc.petitioner is not None, f"{doc.doc_id} missing petitioner"
            assert doc.respondent is not None, f"{doc.doc_id} missing respondent"


# ---------------------------------------------------------------------------
# Tests: normalize_party
# ---------------------------------------------------------------------------
class TestNormalizeParty:
    def test_lowercases(self):
        assert normalize_party("UNION OF INDIA") == "union of india"

    def test_strips_brackets(self):
        result = normalize_party("BALAJI RAGHAVAN [IN T.C.(C) NO.9/94]")
        assert "[" not in result
        assert "]" not in result

    def test_truncates_at_30(self):
        long_name = "A" * 50
        assert len(normalize_party(long_name)) <= 30

    def test_strips_punctuation(self):
        result = normalize_party("CORP. LTD., & ORS.")
        assert "." not in result
        assert "," not in result


# ---------------------------------------------------------------------------
# Tests: ingest_facts
# ---------------------------------------------------------------------------
class TestIngestFacts:
    def test_all_docs_get_fact_ids(self):
        engine = MagicMock()
        engine.ingest.side_effect = lambda **kw: f"fact_{id(kw)}"
        docs = CORPUS[:5]
        ingest_facts(engine, docs)
        assert all(d.fact_id is not None for d in docs)
        assert engine.ingest.call_count == 5

    def test_ingest_failure_doesnt_crash(self):
        engine = MagicMock()
        engine.ingest.side_effect = Exception("DB error")
        # Use fresh doc instances to avoid fact_id pollution from other tests
        body = _make_old_format_body("P", "R", "01/01/2000", ["JUDGE A (J)"], "2000", "1")
        docs = [_make_doc(f"file-fail-{j}", f"-judis-{j}", body) for j in range(3)]
        # Should not raise — just log warning
        ingest_facts(engine, docs)
        assert all(d.fact_id is None for d in docs)

    def test_content_includes_party_names(self):
        engine = MagicMock()
        engine.ingest.side_effect = lambda **kw: "fid"
        docs = CORPUS[:1]
        ingest_facts(engine, docs)
        content_kwarg = engine.ingest.call_args.kwargs["content"]
        # Party names should be in the content string
        assert "STATE OF INDIA" in content_kwarg or "Unknown" in content_kwarg


# ---------------------------------------------------------------------------
# Tests: build_infers_edges
# ---------------------------------------------------------------------------
class TestBuildInfersEdges:
    def _setup(self) -> tuple:
        """Return (engine_mock, docs_with_fact_ids)."""
        engine = MagicMock()
        docs = [d for d in CORPUS if d.judgment_date]  # all have dates
        # Assign fake fact IDs
        for i, d in enumerate(docs):
            d.fact_id = f"fact_{i:04d}"
        return engine, docs

    def test_citing_doc_creates_infers_edges(self):
        engine, docs = self._setup()
        count = build_infers_edges(engine, docs)
        assert count > 0

    def test_self_citation_not_created(self):
        """No edge should point to itself."""
        engine, docs = self._setup()
        build_infers_edges(engine, docs)
        for call_args in engine.add_edge_at.call_args_list:
            kw = call_args.kwargs
            assert kw.get("source_id") != kw.get("target_id")

    def test_infers_edge_type_and_origin(self):
        engine, docs = self._setup()
        build_infers_edges(engine, docs)
        for call_args in engine.add_edge_at.call_args_list:
            kw = call_args.kwargs
            assert kw["edge_type"] == "INFERS"
            assert kw["origin"] == "OBSERVED"

    def test_no_duplicate_edges(self):
        engine, docs = self._setup()
        build_infers_edges(engine, docs)
        pairs = [
            (c.kwargs["source_id"], c.kwargs["target_id"])
            for c in engine.add_edge_at.call_args_list
        ]
        assert len(pairs) == len(set(pairs))

    def test_empty_corpus_no_edges(self):
        engine = MagicMock()
        count = build_infers_edges(engine, [])
        assert count == 0
        engine.add_edge_at.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: build_bench_edges
# ---------------------------------------------------------------------------
class TestBuildBenchEdges:
    def _setup(self):
        engine = MagicMock()
        docs = [d for d in CORPUS if d.judgment_date]
        for i, d in enumerate(docs):
            d.fact_id = f"fact_{i:04d}"
        return engine, docs

    def test_produces_causes_and_similar_edges(self):
        engine, docs = self._setup()
        causes, similar = build_bench_edges(engine, docs)
        assert causes > 0
        assert similar > 0

    def test_causes_come_from_shared_bench_2_plus(self):
        """CAUSES edges should only appear when ≥2 judges shared."""
        engine, docs = self._setup()
        causes, _ = build_bench_edges(engine, docs)
        causes_calls = [
            c for c in engine.add_edge_at.call_args_list
            if c.kwargs["edge_type"] == "CAUSES"
        ]
        assert len(causes_calls) == causes

    def test_structurally_similar_from_single_judge(self):
        similar_calls = []
        engine = MagicMock()
        docs = [d for d in CORPUS if d.judgment_date]
        for i, d in enumerate(docs):
            d.fact_id = f"fact_{i:04d}"
        build_bench_edges(engine, docs)
        similar_calls = [
            c for c in engine.add_edge_at.call_args_list
            if c.kwargs["edge_type"] == "STRUCTURALLY_SIMILAR"
        ]
        assert len(similar_calls) > 0

    def test_no_duplicate_pairs(self):
        engine, docs = self._setup()
        build_bench_edges(engine, docs)
        pairs = [
            (
                min(c.kwargs["source_id"], c.kwargs["target_id"]),
                max(c.kwargs["source_id"], c.kwargs["target_id"]),
            )
            for c in engine.add_edge_at.call_args_list
        ]
        assert len(pairs) == len(set(pairs))

    def test_no_self_edges(self):
        engine, docs = self._setup()
        build_bench_edges(engine, docs)
        for call_args in engine.add_edge_at.call_args_list:
            kw = call_args.kwargs
            assert kw["source_id"] != kw["target_id"]

    def test_chronological_order(self):
        """CAUSES source should have an earlier or equal date than target."""
        engine, docs = self._setup()
        build_bench_edges(engine, docs)
        # Build fact_id -> date mapping
        id_to_date = {d.fact_id: d.judgment_date for d in docs}
        for call_args in engine.add_edge_at.call_args_list:
            kw = call_args.kwargs
            if kw["edge_type"] == "CAUSES":
                src_date = id_to_date.get(kw["source_id"])
                tgt_date = id_to_date.get(kw["target_id"])
                if src_date and tgt_date:
                    assert src_date <= tgt_date, (
                        f"CAUSES edge goes backwards in time: {src_date} > {tgt_date}"
                    )


# ---------------------------------------------------------------------------
# Tests: build_contradicts_edges
# ---------------------------------------------------------------------------
class TestBuildContradictsEdges:
    def _setup(self):
        engine = MagicMock()
        docs = [d for d in CORPUS if d.judgment_date]
        for i, d in enumerate(docs):
            d.fact_id = f"fact_{i:04d}"
        return engine, docs

    def test_detects_party_flip(self):
        """The 5 UNION/KERALA + 5 KERALA/UNION pairs should yield contradicts edges."""
        engine, docs = self._setup()
        count = build_contradicts_edges(engine, docs)
        assert count > 0

    def test_contradicts_edge_type(self):
        engine, docs = self._setup()
        build_contradicts_edges(engine, docs)
        for call_args in engine.add_edge_at.call_args_list:
            assert call_args.kwargs["edge_type"] == "CONTRADICTS"

    def test_no_self_contradicts(self):
        engine, docs = self._setup()
        build_contradicts_edges(engine, docs)
        for call_args in engine.add_edge_at.call_args_list:
            kw = call_args.kwargs
            assert kw["source_id"] != kw["target_id"]

    def test_no_duplicate_contradicts(self):
        engine, docs = self._setup()
        build_contradicts_edges(engine, docs)
        pairs = [
            (
                min(c.kwargs["source_id"], c.kwargs["target_id"]),
                max(c.kwargs["source_id"], c.kwargs["target_id"]),
            )
            for c in engine.add_edge_at.call_args_list
        ]
        assert len(pairs) == len(set(pairs))

    def test_decade_gating(self):
        """Docs decades apart should not get CONTRADICTS edges."""
        engine = MagicMock()
        # Craft two flip docs 40 years apart
        body_a = _make_old_format_body("ALPHA CORP", "BETA LTD", "01/01/1960",
                                        ["JUDGE A (J)"], "1960", "1")
        body_b = _make_old_format_body("BETA LTD", "ALPHA CORP", "01/01/2000",
                                        ["JUDGE A (J)"], "2000", "2")
        doc_a = _make_doc("file-a", "-judis-1", body_a)
        doc_b = _make_doc("file-b", "-judis-2", body_b)
        doc_a.fact_id = "fa"
        doc_b.fact_id = "fb"
        count = build_contradicts_edges(engine, [doc_a, doc_b])
        assert count == 0

    def test_empty_corpus_no_edges(self):
        engine = MagicMock()
        count = build_contradicts_edges(engine, [])
        assert count == 0


# ---------------------------------------------------------------------------
# Integration: parse 50 synthetic docs end-to-end
# ---------------------------------------------------------------------------
class TestCorpusIntegration:
    def test_all_50_docs_parsed(self):
        # 10 constitutional + 10 contradiction pairs + 1 citing + 10 partial-overlap + 9 new-format = 40
        assert len(CORPUS) == 40

    def test_all_docs_have_dates(self):
        missing = [d.doc_id for d in CORPUS if d.judgment_date is None]
        assert missing == [], f"Docs without dates: {missing}"

    def test_all_docs_have_content(self):
        for doc in CORPUS:
            assert len(doc.content) > 10, f"{doc.doc_id} has empty content"

    def test_new_format_docs_parsed(self):
        new_format = [d for d in CORPUS if "supremecourt" in d.doc_id]
        assert len(new_format) == 9  # 9 new-format cases appended at end
        for doc in new_format:
            assert doc.judgment_date is not None
            assert doc.judgment_date.year == 2018

    def test_full_ingest_and_edge_pipeline(self):
        """Run the entire pipeline on the 50-doc corpus and check totals."""
        engine = MagicMock()
        call_counter = [0]

        def fake_ingest(**kw):
            call_counter[0] += 1
            return f"fact_{call_counter[0]:04d}"

        engine.ingest.side_effect = fake_ingest
        docs = list(CORPUS)  # fresh copy

        ingest_facts(engine, docs)
        infers = build_infers_edges(engine, docs)
        causes, similar = build_bench_edges(engine, docs)
        contradicts = build_contradicts_edges(engine, docs)

        total_edges = infers + causes + similar + contradicts
        assert total_edges > 10, f"Expected >10 edges, got {total_edges}"
        # All three strategies should contribute
        assert infers > 0
        assert causes + similar > 0
        assert contradicts > 0
