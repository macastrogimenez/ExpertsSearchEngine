"""16-condition abstract field boost experiment.
From backend/:
python -u ../testing/evaluate_abstract_grid.py --queries ../testing/test_queries_final.csv --output ../testing/bm25_abstract_grid_results

Field boosts are query boosts (Whoosh MultifieldParser), not BM25F internal field weights.
"""
from __future__ import annotations
import argparse, csv, json, sys
from collections import defaultdict
from pathlib import Path
from whoosh import index
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.scoring import BM25F

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
from bm25_baseline import INDEX_PATH, SEARCH_FIELDS
from bm25_stemming import STEM_INDEX_PATH, validate
from bm25_stopwords import STOP_INDEX_PATH
from bm25_standard_stopwords import STANDARD_STOP_INDEX_PATH
from bm25_discounted import discounted_combsum
from evaluate_bm25 import known_positive_metrics, normalize_name

INDEXES = {
    "stem0_stop0": INDEX_PATH,
    "stem0_stop1": STANDARD_STOP_INDEX_PATH,
    "stem1_stop0": STEM_INDEX_PATH,
    "stem1_stop1": STOP_INDEX_PATH,
}
WEIGHTS = (1, 2, 4, 8)

def save_csv(path, rows):
    if not rows: return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def search(ix, query, abstract_weight, depth):
    boosts = {field: 1.0 for field in SEARCH_FIELDS}
    boosts["abstract"] = float(abstract_weight)
    parser = MultifieldParser(SEARCH_FIELDS, schema=ix.schema, group=OrGroup, fieldboosts=boosts)
    parsed = parser.parse(query)
    with ix.searcher(weighting=BM25F(B=0.75, K1=1.2)) as s:
        hits = s.search(parsed, limit=depth)
        docs = []
        for hit in hits:
            doc = json.loads(hit["payload"])
            doc["bm25_score"] = float(hit.score)
            docs.append(doc)
    return docs

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--queries", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--depth", type=int, default=100)
    p.add_argument("--top-k", type=int, default=10)
    args = p.parse_args()
    if args.depth < 1 or args.top_k < 1: p.error("depth and top-k must be positive")
    with args.queries.open(newline="", encoding="utf-8-sig") as f:
        queries = list(csv.DictReader(f))
    if not queries or not {"query","query_type","expected_experts"}.issubset(queries[0]):
        p.error("Missing query, query_type, or expected_experts column")
    print("Checking all four indexes against the frozen baseline...", flush=True)
    for name, path in INDEXES.items():
        if not path.exists(): raise FileNotFoundError(path)
        if name != "stem0_stop0":
            print(name, validate(INDEX_PATH, path), flush=True)
    people = json.loads((INDEX_PATH / "people.json").read_text(encoding="utf-8"))
    indexes = {name: index.open_dir(path) for name, path in INDEXES.items()}
    metrics, rankings = [], []
    cache = {}
    for qid, row in enumerate(queries, 1):
        query = row["query"].strip()
        if not query: continue
        expected = {normalize_name(x) for x in row["expected_experts"].split(";") if x.strip()}
        for name, ix in indexes.items():
            for weight in WEIGHTS:
                key = (name, weight, query)
                if key not in cache:
                    docs = search(ix, query, weight, args.depth)
                    ranked = discounted_combsum(docs, people, limit=args.top_k)
                    cache[key] = (len(docs), ranked)
                doc_count, ranked = cache[key]
                config = f"{name}_abs{weight}"
                metric = known_positive_metrics(ranked, expected, args.top_k)
                metrics.append(dict(query_id=qid, query=query, query_type=row["query_type"],
                                    configuration=config, preprocessing=name,
                                    stemming=int(name[4]), stopwords=int(name[-1]),
                                    abstract_weight=weight, retrieved_document_count=doc_count,
                                    expected_expert_count=len(expected), **metric))
                for rank, expert in enumerate(ranked, 1):
                    rankings.append(dict(query_id=qid, query=query, query_type=row["query_type"],
                                         configuration=config, rank=rank,
                                         researcher_uuid=expert["uuid"], researcher_name=expert["name"],
                                         score=expert["score"],
                                         known_positive=int(normalize_name(expert["name"]) in expected)))
        if qid % 10 == 0 or qid == len(queries):
            print(f"Processed {qid}/{len(queries)}", flush=True)
    summary = []
    metric_cols = ("known_recall_at_k", "known_mrr_at_k", "known_ndcg_at_k")
    groups = defaultdict(list)
    for row in metrics:
        groups[(row["configuration"], row["query_type"])].append(row)
        groups[(row["configuration"], "overall")].append(row)
    for (config, group), rows in sorted(groups.items()):
        sample = rows[0]
        summary.append(dict(configuration=config, preprocessing=sample["preprocessing"],
                            stemming=sample["stemming"], stopwords=sample["stopwords"],
                            abstract_weight=sample["abstract_weight"], query_type=group,
                            queries=len(rows), **{m:sum(float(r[m]) for r in rows)/len(rows) for m in metric_cols}))
    args.output.mkdir(parents=True, exist_ok=True)
    save_csv(args.output / "summary.csv", summary)
    save_csv(args.output / "metrics.csv", metrics)
    save_csv(args.output / "rankings.csv", rankings)
    config = dict(queries=len(queries), depth=args.depth, top_k=args.top_k,
                  abstract_weights=WEIGHTS, indexes={k:str(v) for k,v in INDEXES.items()},
                  search_fields=list(SEARCH_FIELDS), title_weight=1,
                  other_field_weights=1, aggregation="discounted_combsum",
                  bm25f=dict(B=0.75,K1=1.2),
                  field_weight_method="Whoosh MultifieldParser fieldboosts (query-time boosts)",
                  note="Known-positive labels are incomplete; related queries may be dependent")
    (args.output/"run_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print("Top overall configurations:")
    for r in sorted((r for r in summary if r["query_type"]=="overall"),
                    key=lambda r:r["known_ndcg_at_k"], reverse=True)[:8]:
        print(r["configuration"], round(r["known_ndcg_at_k"], 5))
    print("Saved to", args.output.resolve())

if __name__ == "__main__":
    main()
