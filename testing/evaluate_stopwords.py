"""Evaluate stemming with and without stopword removal.

Run from backend/:
    python -u ../testing/evaluate_stopwords.py \
        --queries ../testing/test_queries_final.csv \
        --output ../testing/bm25_stopword_results
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

from collections import defaultdict
from pathlib import Path


BACKEND_DIR = (
    Path(__file__).resolve().parent.parent / "backend"
)

sys.path.insert(0, str(BACKEND_DIR))


from bm25_baseline import search_documents
from bm25_discounted import discounted_combsum
from bm25_stemming import STEM_INDEX_PATH, validate
from bm25_stopwords import STOP_INDEX_PATH

from evaluate_bm25 import (
    known_positive_metrics,
    normalize_name,
)


def save_csv(path, rows):
    if not rows:
        return

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0]),
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--queries",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("bm25_stopword_results"),
    )

    parser.add_argument(
        "--baseline-index",
        type=Path,
        default=STEM_INDEX_PATH,
    )

    parser.add_argument(
        "--stopword-index",
        type=Path,
        default=STOP_INDEX_PATH,
    )

    parser.add_argument(
        "--document-limit",
        type=int,
        default=100,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )

    args = parser.parse_args()

    if args.document_limit < 1 or args.limit < 1:
        parser.error("Limits must be positive")

    print("Validating index equivalence...", flush=True)

    validation = validate(
        args.baseline_index,
        args.stopword_index,
    )

    print(
        json.dumps(validation, indent=2),
        flush=True,
    )

    with args.queries.open(
        newline="",
        encoding="utf-8-sig",
    ) as f:
        reader = csv.DictReader(f)

        required = {
            "query",
            "query_type",
            "expected_experts",
        }

        if not required.issubset(reader.fieldnames or []):
            parser.error(
                "CSV must contain query, query_type, "
                "and expected_experts"
            )

        queries = list(reader)

    people = json.loads(
        (
            args.baseline_index / "people.json"
        ).read_text(encoding="utf-8")
    )

    paths = {
        "stemming_no_stopwords": args.baseline_index,
        "stemming_with_stopwords": args.stopword_index,
    }

    cache = {}

    metric_rows = []
    ranking_rows = []
    comparison_rows = []

    for qid, row in enumerate(queries, start=1):
        query = row["query"].strip()

        if not query:
            continue

        expected = {
            normalize_name(name)
            for name in row["expected_experts"].split(";")
            if name.strip()
        }

        rankings = {}

        for variant, path in paths.items():
            key = (variant, query)

            if key not in cache:
                documents = search_documents(
                    query,
                    limit=args.document_limit,
                    path=path,
                )

                ranked = discounted_combsum(
                    documents,
                    people,
                    limit=args.limit,
                )

                cache[key] = (
                    len(documents),
                    ranked,
                )

            document_count, ranked = cache[key]

            rankings[variant] = ranked

            scores = known_positive_metrics(
                ranked,
                expected,
                args.limit,
            )

            metric_rows.append({
                "query_id": qid,
                "query": query,
                "query_type": row["query_type"],
                "variant": variant,
                "expected_expert_count": len(expected),
                "retrieved_document_count": document_count,
                **scores,
            })

            for rank, expert in enumerate(ranked, start=1):
                ranking_rows.append({
                    "query_id": qid,
                    "query": query,
                    "query_type": row["query_type"],
                    "variant": variant,
                    "rank": rank,
                    "researcher_uuid": expert["uuid"],
                    "researcher_name": expert["name"],
                    "score": expert["score"],
                    "known_positive": int(
                        normalize_name(expert["name"])
                        in expected
                    ),
                })

        # Compare top-10 researcher sets
        baseline = rankings["stemming_no_stopwords"]
        stopwords = rankings["stemming_with_stopwords"]

        baseline_ids = {
            expert["uuid"] for expert in baseline
        }

        stopword_ids = {
            expert["uuid"] for expert in stopwords
        }

        same_top_1 = int(
            bool(baseline and stopwords)
            and baseline[0]["uuid"]
            == stopwords[0]["uuid"]
        )

        comparison_rows.append({
            "query_id": qid,
            "query": query,
            "query_type": row["query_type"],
            "top_k_overlap": len(
                baseline_ids & stopword_ids
            ),
            "same_top_1": same_top_1,
        })

        if (
            qid == 1
            or qid % 10 == 0
            or qid == len(queries)
        ):
            print(
                f"Processed {qid}/{len(queries)} queries",
                flush=True,
            )

    # Calculate mean metrics
    groups = defaultdict(lambda: defaultdict(list))

    for row in metric_rows:
        for metric in (
            "known_recall_at_k",
            "known_mrr_at_k",
            "known_ndcg_at_k",
        ):
            groups[
                (row["variant"], row["query_type"])
            ][metric].append(row[metric])

            groups[
                (row["variant"], "overall")
            ][metric].append(row[metric])

    summary = []

    for (variant, query_type), values in sorted(
        groups.items()
    ):
        summary.append({
            "variant": variant,
            "query_type": query_type,
            "queries": len(
                values["known_ndcg_at_k"]
            ),
            **{
                metric: sum(numbers) / len(numbers)
                for metric, numbers in values.items()
            },
        })

    # Save results
    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_csv(
        args.output / "summary.csv",
        summary,
    )

    save_csv(
        args.output / "metrics.csv",
        metric_rows,
    )

    save_csv(
        args.output / "rankings.csv",
        ranking_rows,
    )

    save_csv(
        args.output / "comparison.csv",
        comparison_rows,
    )

    config = {
        "queries": len(queries),
        "unique_queries": len({
            row["query"].strip()
            for row in queries
            if row["query"].strip()
        }),
        "document_limit": args.document_limit,
        "top_k": args.limit,
        "aggregation": "discounted_combsum",
        "stemming": "enabled in both",
        "stopwords": {
            "stemming_no_stopwords": "disabled",
            "stemming_with_stopwords": (
                "Whoosh English STOP_WORDS"
            ),
        },
        "baseline_index": str(args.baseline_index),
        "stopword_index": str(args.stopword_index),
        "evaluation_note": (
            "Incomplete known-positive judgments; "
            "not exhaustive relevance labels."
        ),
    }

    (
        args.output / "run_config.json"
    ).write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )

    print("\nOVERALL RESULTS", flush=True)

    for row in summary:
        if row["query_type"] == "overall":
            print(
                f"{row['variant']:25s} "
                f"Recall={row['known_recall_at_k']:.4f} "
                f"MRR={row['known_mrr_at_k']:.4f} "
                f"nDCG={row['known_ndcg_at_k']:.4f}",
                flush=True,
            )

    print(
        f"\nResults saved to: {args.output.resolve()}",
        flush=True,
    )


if __name__ == "__main__":
    main()