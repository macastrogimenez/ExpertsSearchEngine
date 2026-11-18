"""Experiment 8: expert score aggregation, using a frozen Whoosh index.

From backend/:
 python -u ../testing/evaluate_aggregation.py --queries ../testing/test_queries_final.csv --output ../testing/bm25_aggregation_results

Methods use the same top-100 BM25F documents; raw CombMIN includes every
matched document (even weak matches). Course discounting applies only to
Discounted CombSUM, consistent with the existing implementation.
"""
from __future__ import annotations
import argparse, csv, json, math, sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / 'backend'
sys.path.insert(0, str(BACKEND))
from bm25_baseline import search_documents
from bm25_discounted import discounted_combsum
from bm25_stopwords import STOP_INDEX_PATH
from evaluate_bm25 import known_positive_metrics, normalize_name

METHODS = ('combmax', 'combmin', 'combsum', 'combmnz', 'combmean', 'discounted_combsum')
METRICS = ('known_ndcg_at_k', 'known_mrr_at_k', 'known_recall_at_k', 'known_hits_at_k')

def aggregate(documents, people, method, limit=10):
    if method == 'discounted_combsum':
        return discounted_combsum(documents, people, limit=limit)
    scores = defaultdict(list)
    for doc in documents:
        s = float(doc['bm25_score'])
        if not math.isfinite(s) or s < 0:
            raise ValueError(f'Invalid BM25 score for {doc["document_id"]}: {s}')
        if s <= 0:
            continue
        for uid in set(doc['researcher_uuids']):
            if uid in people:
                scores[uid].append(s)
    def combine(values):
        if method == 'combmax': return max(values)
        if method == 'combmin': return min(values)
        if method == 'combsum': return sum(values)
        if method == 'combmnz': return sum(values) * len(values)
        if method == 'combmean': return sum(values) / len(values)
        raise ValueError(method)
    ranked = sorted(((uid, combine(v)) for uid, v in scores.items()),
                    key=lambda x: (-x[1], x[0]))[:limit]
    return [{**people[uid], 'score': score, 'matched_document_count': len(scores[uid])}
            for uid, score in ranked]

def write_csv(path, rows):
    if not rows: return
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--queries', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--index', type=Path, default=STOP_INDEX_PATH)
    p.add_argument('--depth', type=int, default=100)
    p.add_argument('--top-k', type=int, default=10)
    args = p.parse_args()
    if args.depth < 1 or args.top_k < 1: p.error('depth and top-k must be positive')
    if not args.index.exists(): raise FileNotFoundError(args.index)
    people = json.loads((args.index / 'people.json').read_text(encoding='utf-8'))
    with args.queries.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not {'query','query_type','expected_experts'}.issubset(reader.fieldnames or []):
            p.error('CSV must contain query, query_type, expected_experts')
        queries = list(reader)
    metrics, rankings, cache = [], [], {}
    for qid, row in enumerate(queries, 1):
        query = row['query'].strip()
        if not query: continue
        expected = {normalize_name(n) for n in row['expected_experts'].split(';') if n.strip()}
        if query not in cache:
            docs = search_documents(query, limit=args.depth, path=args.index)
            cache[query] = (len(docs), {m:aggregate(docs, people, m, args.top_k) for m in METHODS})
        n_docs, results = cache[query]
        for method, ranked in results.items():
            vals = known_positive_metrics(ranked, expected, args.top_k)
            metrics.append(dict(query_id=qid, query=query, query_type=row['query_type'],
                                method=method, retrieved_document_count=n_docs,
                                expected_expert_count=len(expected), **vals))
            for rank, expert in enumerate(ranked, 1):
                rankings.append(dict(query_id=qid, query=query, query_type=row['query_type'],
                                     method=method, rank=rank, researcher_uuid=expert['uuid'],
                                     researcher_name=expert['name'], score=expert['score'],
                                     matched_document_count=expert['matched_document_count'],
                                     known_positive=int(normalize_name(expert['name']) in expected)))
        if qid % 25 == 0 or qid == len(queries):
            print(f'Processed {qid}/{len(queries)} queries', flush=True)
    summary=[]
    for method in METHODS:
        for group in ['overall'] + sorted(set(r['query_type'] for r in metrics)):
            subset = [r for r in metrics if r['method']==method and
                      (group=='overall' or r['query_type']==group)]
            if not subset: continue
            summary.append(dict(method=method, query_type=group, queries=len(subset),
                                **{m:sum(float(r[m]) for r in subset)/len(subset) for m in METRICS}))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output/'metrics.csv', metrics)
    write_csv(args.output/'rankings.csv', rankings)
    write_csv(args.output/'summary.csv', summary)
    (args.output/'run_config.json').write_text(json.dumps({
        'index':str(args.index),'queries':len(queries),'depth':args.depth,
        'top_k':args.top_k,'methods':METHODS,'bm25f':{'B':0.75,'K1':1.2},
        'preprocessing':'stemming and stopword removal',
        'field_boosts':'all fields = 1 (baseline MultifieldParser)',
        'course_discounting':'only discounted_combsum',
        'combmin_definition':'minimum positive score among retrieved matching documents',
        'combmnz_definition':'sum(scores) * number of matching documents',
        'note':'Known-positive labels incomplete; queries may be dependent.'
    },indent=2), encoding='utf-8')
    print('\nOverall results (sorted by known-positive nDCG@10):')
    for r in sorted((r for r in summary if r['query_type']=='overall'),
                    key=lambda r:r['known_ndcg_at_k'],reverse=True):
        print(f"{r['method']:20} nDCG={r['known_ndcg_at_k']:.4f} MRR={r['known_mrr_at_k']:.4f} Recall={r['known_recall_at_k']:.4f}")
    print('Saved to:',args.output.resolve())

if __name__=='__main__': main()
