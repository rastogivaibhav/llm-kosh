#!/usr/bin/env python3
"""
Batch causal extraction from legal corpus.

Usage:
    python scripts/ingest_legal_corpus.py --doc-list test_documents_200.txt --cartridge <path>
    python scripts/ingest_legal_corpus.py --corpus-dir <dir> --cartridge <path>
"""
import argparse
import time
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="Ingest legal corpus into causal DAG")
    parser.add_argument("--doc-list", help="Path to text file with one document path per line")
    parser.add_argument("--corpus-dir", help="Directory to scan for .md files")
    parser.add_argument("--cartridge", required=True, help="Path to llm-kosh cartridge root")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--max-docs", type=int, default=0, help="0 = all")
    args = parser.parse_args()

    from llm_kosh.engine.reasoning import ReasoningEngine
    from llm_kosh.engine.extraction import process_document

    engine = ReasoningEngine(Path(args.cartridge))

    # Collect document paths
    docs = []
    if args.doc_list:
        with open(args.doc_list, encoding="utf-8") as f:
            docs = [line.strip() for line in f if line.strip()]
    elif args.corpus_dir:
        docs = [str(p) for p in Path(args.corpus_dir).rglob("*.md")]

    if args.max_docs:
        docs = docs[: args.max_docs]

    total = len(docs)
    print(f"Processing {total} documents in batches of {args.batch_size}")

    facts_added = 0
    skipped = 0
    t_start = time.time()

    for i, filepath in enumerate(docs):
        try:
            fact_id = process_document(filepath, engine)
            if fact_id:
                facts_added += 1
            else:
                skipped += 1
        except Exception as e:
            skipped += 1
            print(f"  ERROR {Path(filepath).name}: {e}")

        # Batch snapshot
        if (i + 1) % args.batch_size == 0:
            engine.dag.save_snapshot()
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(
                f"  Batch {(i + 1) // args.batch_size}: {i + 1}/{total} docs, "
                f"{facts_added} facts, {skipped} skipped, "
                f"ETA {eta / 60:.1f}m"
            )

    # Final snapshot
    engine.dag.save_snapshot()
    elapsed = time.time() - t_start
    print(f"\nDone. {facts_added} facts added, {skipped} skipped in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
