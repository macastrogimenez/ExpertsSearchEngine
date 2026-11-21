"""Grid search for BM25F document retrieval depth.

Run from backend/:
python -u ../testing/evaluate_retrieval_depth.py \
    --queries ../testing/test_queries_final.csv \
    --output ../testing/bm25_depth_results
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from bm25_baseline import INDEX_PATH, search_documents, combsum
from bm25_discounted import discounted_combsum
from evaluate_bm25 import known_positive_metrics, normalize_name


def save_csv(path, rows):
    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="BM25F retrieval-depth grid search"
    )

    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("bm25_depth_results"),
    )
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    parser.add_argument(
        "--depths",
        type=int,
        nargs="+",
        default=[10, 25, 50, 75, 100, 150, 250, 500],
    )
    parser.add_argument("--top-k", type=int, default=10)

    args = parser.parse_args()

    depths = sorted(set(args.depths))
    methods = {
        "combsum": combsum,
        "discounted": discounted_combsum,
    }

    if not depths or min(depths) < 1 or args.top_k < 1:
        parser.error("Depths and top-k must be positive")

    people = json.loads(
        (args.index / "people.json").read_text(encoding="utf-8")
    )

    with args.queries.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"query", "query_type", "expected_experts"}

        if not required.issubset(reader.fieldnames or []):
            parser.error(
                f"Missing columns: {required - set(reader.fieldnames or [])}"
            )

        queries = list(reader)

    print(
        f"Loaded {len(queries)} queries. Testing depths: {depths}",
        flush=True,
    )

    cache = {}
    metric_rows = []
    coverage_rows = []

    for qid, row in enumerate(queries, start=1):
        query = row["query"].strip()

        if not query:
            continue

        expected = {
            normalize_name(name)
            for name in row["expected_experts"].split(";")
            if name.strip()
        }

        # Retrieve up to the maximum depth once per unique query.
        if query not in cache:
            cache[query] = search_documents(
                query,
                limit=max(depths),
                path=args.index,
            )

        all_docs = cache[query]

        for depth in depths:
            docs = all_docs[:depth]

            for method_name, aggregate in methods.items():
                # Rank all candidate researchers, not just the top 10.
                ranking = aggregate(
                    docs,
                    people,
                    limit=len(people),
                )

                top_ranking = ranking[:args.top_k]

                measures = known_positive_metrics(
                    top_ranking,
                    expected,
                    args.top_k,
                )

                metric_rows.append({
                    "query_id": qid,
                    "query": query,
                    "query_type": row["query_type"],
                    "depth": depth,
                    "method": method_name,
                    "expected_expert_count": len(expected),
                    "retrieved_document_count": len(docs),
                    "candidate_researcher_count": len(ranking),
                    **measures,
                })

                ranks = {
                    normalize_name(person["name"]): rank
                    for rank, person in enumerate(ranking, start=1)
                }

                for name in sorted(expected):
                    rank = ranks.get(name)

                    if rank is None:
                        status = "not_retrieved"
                    elif rank <= args.top_k:
                        status = "in_top_k"
                    else:
                        status = "below_top_k"

                    coverage_rows.append({
                        "query_id": qid,
                        "query_type": row["query_type"],
                        "depth": depth,
                        "method": method_name,
                        "expected_expert": name,
                        "researcher_rank": (
                            rank if rank is not None else ""
                        ),
                        "status": status,
                    })

        if qid == 1 or qid % 10 == 0 or qid == len(queries):
            print(
                f"Processed {qid}/{len(queries)} queries "
                f"({len(cache)} unique)",
                flush=True,
            )

    # Aggregate metrics by method, depth, and query type.
    groups = defaultdict(list)

    for row in metric_rows:
        groups[(row["method"], row["depth"], "overall")].append(row)
        groups[
            (row["method"], row["depth"], row["query_type"])
        ].append(row)

    fields = [
        "known_recall_at_k",
        "known_mrr_at_k",
        "known_ndcg_at_k",
        "retrieved_document_count",
        "candidate_researcher_count",
    ]

    summary = []

    for (method, depth, query_type), rows in sorted(groups.items()):
        summary.append({
            "method": method,
            "depth": depth,
            "query_type": query_type,
            "queries": len(rows),
            **{
                field: sum(r[field] for r in rows) / len(rows)
                for field in fields
            },
        })

    args.output.mkdir(parents=True, exist_ok=True)

    save_csv(args.output / "summary.csv", summary)
    save_csv(args.output / "metrics.csv", metric_rows)
    save_csv(args.output / "expert_coverage.csv", coverage_rows)

    config = {
        "queries": len(queries),
        "unique_queries": len(cache),
        "depths": depths,
        "top_k": args.top_k,
        "methods": list(methods),
        "index": str(args.index),
        "note": (
            "Known-positive relevance judgments are incomplete. "
            "The query set is used for exploratory parameter tuning."
        ),
    }

    (args.output / "run_config.json").write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )

    print("\nOVERALL RESULTS", flush=True)

    for row in summary:
        if row["query_type"] == "overall":
            print(
                f"{row['method']:10s} "
                f"depth={row['depth']:3d} "
                f"Recall={row['known_recall_at_k']:.4f} "
                f"MRR={row['known_mrr_at_k']:.4f} "
                f"nDCG={row['known_ndcg_at_k']:.4f}",
                flush=True,
            )

    print(f"\nResults saved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()