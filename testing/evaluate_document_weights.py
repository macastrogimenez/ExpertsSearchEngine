"""Experiment 9: document-type multipliers on course-discounted CombSUM.

Run from backend/:
 python -u ../testing/evaluate_document_weights.py --queries ../testing/test_queries_final.csv --output ../testing/bm25_document_weight_results

Multipliers apply to each paper/project score and to each *discounted*
course contribution. Retrieval is identical across configurations.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / 'backend'
sys.path.insert(0, str(BACKEND))
from bm25_baseline import search_documents
from bm25_discounted import course_group_key, discounted_combsum
from bm25_stopwords import STOP_INDEX_PATH
from evaluate_bm25 import known_positive_metrics, normalize_name

# Full factorial grid: 3 paper weights x 3 project weights x 3 course weights.
# Preserve the name "baseline" for compatibility with the analysis notebook.
CONFIGS = {
    ('baseline' if (paper, project, course) == (1, 1, 1)
     else f'paper{paper}_project{project}_course{course}'):
    {'paper': float(paper), 'project': float(project), 'course': float(course)}
    for paper in (1, 2, 3)
    for project in (1, 2, 3)
    for course in (1, 2, 3)
}

METRICS = ('known_ndcg_at_k', 'known_mrr_at_k', 'known_recall_at_k', 'known_hits_at_k')


def aggregate(documents, people, weights, limit=10):
    """Harmonic course-title discount, then type weighting, per researcher."""
    scores = defaultdict(float)
    counts = defaultdict(int)
    groups = defaultdict(lambda: defaultdict(list))
    for doc in documents:
        score = float(doc['bm25_score'])
        if not math.isfinite(score) or score < 0:
            raise ValueError(f"Invalid BM25 score: {doc['document_id']}")
        kind = doc['document_type']
        if kind not in weights:
            raise ValueError(f'Unexpected document type: {kind}')
        for uid in set(doc['researcher_uuids']):
            if uid not in people:
                continue
            counts[uid] += 1
            if kind == 'course':
                key = course_group_key(doc['title'], doc['document_id'])
                groups[uid][key].append((score, doc['document_id']))
            else:
                scores[uid] += score * weights[kind]
    for uid, titles in groups.items():
        for offerings in titles.values():
            for position, (score, _) in enumerate(sorted(offerings, key=lambda x: (-x[0], x[1])), 1):
                scores[uid] += score * weights['course'] / position
    ranked = sorted(counts, key=lambda uid: (-scores[uid], uid))[:limit]
    return [{**people[uid], 'score': scores[uid], 'matched_document_count': counts[uid]}
            for uid in ranked]


def write_csv(path, rows):
    if not rows:
        return
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
    if args.depth < 1 or args.top_k < 1:
        p.error('depth and top-k must be positive')
    if not args.index.exists():
        raise FileNotFoundError(args.index)
    with args.queries.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not {'query', 'query_type', 'expected_experts'}.issubset(reader.fieldnames or []):
            p.error('CSV must contain query, query_type, expected_experts')
        queries = list(reader)
    people = json.loads((args.index / 'people.json').read_text(encoding='utf-8'))
    metrics, rankings, cache = [], [], {}
    for qid, row in enumerate(queries, 1):
        query = row['query'].strip()
        if not query:
            continue
        expected = {normalize_name(n) for n in row['expected_experts'].split(';') if n.strip()}
        if query not in cache:
            docs = search_documents(query, limit=args.depth, path=args.index)
            result = {config: aggregate(docs, people, weights, args.top_k)
                      for config, weights in CONFIGS.items()}
            # Ensure exact baseline parity with the original aggregation implementation.
            original = discounted_combsum(docs, people, limit=args.top_k)
            assert [x['uuid'] for x in original] == [x['uuid'] for x in result['baseline']], (
                f'Baseline mismatch for query: {query}')
            cache[query] = (len(docs), result)
        n_docs, results = cache[query]
        for config, ranked in results.items():
            vals = known_positive_metrics(ranked, expected, args.top_k)
            metrics.append(dict(query_id=qid, query=query, query_type=row['query_type'],
                                configuration=config, retrieved_document_count=n_docs,
                                expected_expert_count=len(expected), **vals))
            for rank, expert in enumerate(ranked, 1):
                rankings.append(dict(query_id=qid, query=query, query_type=row['query_type'],
                                     configuration=config, rank=rank,
                                     researcher_uuid=expert['uuid'], researcher_name=expert['name'],
                                     score=expert['score'], matched_document_count=expert['matched_document_count'],
                                     known_positive=int(normalize_name(expert['name']) in expected)))
        if qid % 25 == 0 or qid == len(queries):
            print(f'Processed {qid}/{len(queries)} queries', flush=True)
    summary = []
    groups = ['overall'] + sorted(set(r['query_type'] for r in metrics))
    for config in CONFIGS:
        for group in groups:
            subset = [r for r in metrics if r['configuration'] == config and
                      (group == 'overall' or r['query_type'] == group)]
            if not subset:
                continue
            summary.append(dict(configuration=config, query_type=group, queries=len(subset),
                                paper_weight=CONFIGS[config]['paper'],
                                project_weight=CONFIGS[config]['project'],
                                course_weight=CONFIGS[config]['course'],
                                **{m:sum(float(r[m]) for r in subset)/len(subset) for m in METRICS}))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output/'metrics.csv', metrics)
    write_csv(args.output/'rankings.csv', rankings)
    write_csv(args.output/'summary.csv', summary)
    (args.output/'run_config.json').write_text(json.dumps({
        'index':str(args.index), 'queries':len(queries), 'depth':args.depth,
        'top_k':args.top_k, 'configurations':CONFIGS,
        'preprocessing':'stemming and stopword removal',
        'field_boosts':'all fields = 1',
        'aggregation':'course-title harmonic-discounted CombSUM',
        'baseline_verified_against_existing_discounted_combsum':True,
        'notes':'Known-positive labels incomplete; queries may share article sources. '
                'Type weights are applied after retrieval; course duplicates retain harmonic discount.'
    }, indent=2), encoding='utf-8')
    print('\nOverall results (sorted by known-positive nDCG@10):')
    for r in sorted((r for r in summary if r['query_type']=='overall'),
                    key=lambda r:r['known_ndcg_at_k'], reverse=True):
        print(f"{r['configuration']:17} nDCG={r['known_ndcg_at_k']:.4f} "
              f"MRR={r['known_mrr_at_k']:.4f} Recall={r['known_recall_at_k']:.4f}")
    print('Saved to:', args.output.resolve())

if __name__ == '__main__':
    main()
