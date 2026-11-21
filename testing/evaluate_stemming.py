"""Compare no-stemming vs stemming with identical BM25F and Discounted CombSUM.

From backend/:
    python -u ../testing/evaluate_stemming.py --queries ../testing/test_queries_final.csv \\
        --output ../testing/bm25_stemming_results
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / 'backend'
sys.path.insert(0, str(BACKEND_DIR))

from bm25_baseline import INDEX_PATH, search_documents
from bm25_discounted import discounted_combsum
from bm25_stemming import STEM_INDEX_PATH, validate

# Reuse the EXACT metric implementation used in the previous BM25 evaluation.
# The existing evaluate_bm25.py is expected in testing/ (or backend/).
try:
    from evaluate_bm25 import known_positive_metrics, normalize_name
except ImportError:
    from testing.evaluate_bm25 import known_positive_metrics, normalize_name


def save_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--queries', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('bm25_stemming_results'))
    p.add_argument('--baseline-index', type=Path, default=INDEX_PATH)
    p.add_argument('--stemming-index', type=Path, default=STEM_INDEX_PATH)
    p.add_argument('--document-limit', type=int, default=100)
    p.add_argument('--limit', type=int, default=10)
    args = p.parse_args()
    if args.limit < 1 or args.document_limit < 1:
        p.error('Limits must be positive')
    print('Validating index equivalence...', flush=True)
    print(json.dumps(validate(args.baseline_index, args.stemming_index), indent=2), flush=True)
    with args.queries.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not {'query', 'query_type', 'expected_experts'}.issubset(reader.fieldnames or []):
            p.error('CSV must contain query, query_type, expected_experts')
        queries = list(reader)
    people = json.loads((args.baseline_index / 'people.json').read_text(encoding='utf-8'))
    cache = {}
    metric_rows, rank_rows, comparison_rows = [], [], []
    paths = {'no_stemming': args.baseline_index, 'stemming': args.stemming_index}
    for qid, row in enumerate(queries, 1):
        query = row['query'].strip()
        if not query:
            continue
        expected = {normalize_name(x) for x in row['expected_experts'].split(';') if x.strip()}
        ranks = {}
        for variant, path in paths.items():
            key = (variant, query)
            if key not in cache:
                docs = search_documents(query, limit=args.document_limit, path=path)
                cache[key] = (len(docs), discounted_combsum(docs, people, limit=args.limit))
            n_docs, ranked = cache[key]
            ranks[variant] = ranked
            metrics = known_positive_metrics(ranked, expected, args.limit)
            metric_rows.append({'query_id': qid, 'query': query, 'query_type': row['query_type'],
                                'variant': variant, 'expected_expert_count': len(expected),
                                'retrieved_document_count': n_docs, **metrics})
            for rank, expert in enumerate(ranked, 1):
                rank_rows.append({'query_id': qid, 'query': query, 'query_type': row['query_type'],
                                  'variant': variant, 'rank': rank, 'researcher_uuid': expert['uuid'],
                                  'researcher_name': expert['name'], 'score': expert['score'],
                                  'known_positive': int(normalize_name(expert['name']) in expected)})
        a = {x['uuid'] for x in ranks['no_stemming']}
        b = {x['uuid'] for x in ranks['stemming']}
        comparison_rows.append({'query_id': qid, 'query': query, 'query_type': row['query_type'],
                                'top_k_overlap': len(a & b),
                                'same_top_1': int(bool(ranks['no_stemming'] and ranks['stemming']) and
                                                  ranks['no_stemming'][0]['uuid'] == ranks['stemming'][0]['uuid'])})
        if qid == 1 or qid % 10 == 0 or qid == len(queries):
            print(f'Processed {qid}/{len(queries)} queries', flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    save_csv(args.output / 'metrics.csv', metric_rows)
    save_csv(args.output / 'rankings.csv', rank_rows)
    save_csv(args.output / 'comparison.csv', comparison_rows)
    means = defaultdict(lambda: defaultdict(list))
    for r in metric_rows:
        for metric in ('known_recall_at_k', 'known_mrr_at_k', 'known_ndcg_at_k'):
            means[(r['variant'], r['query_type'])][metric].append(r[metric])
            means[(r['variant'], 'overall')][metric].append(r[metric])
    summary = []
    for (variant, group), values in sorted(means.items()):
        summary.append({'variant': variant, 'query_type': group, 'queries': len(values['known_ndcg_at_k']),
                        **{metric: sum(nums) / len(nums) for metric, nums in values.items()}})
    save_csv(args.output / 'summary.csv', summary)
    (args.output / 'run_config.json').write_text(json.dumps({
        'queries': len(queries), 'unique_queries': len({r['query'].strip() for r in queries if r['query'].strip()}),
        'document_limit': args.document_limit, 'top_k': args.limit,
        'aggregation': 'discounted_combsum', 'stopwords': 'disabled for both',
        'baseline_index': str(args.baseline_index), 'stemming_index': str(args.stemming_index),
        'evaluation_note': 'Incomplete known-positive judgments; not exhaustive relevance labels'
    }, indent=2), encoding='utf-8')
    print('\nResults saved to:', args.output, flush=True)
    for row in summary:
        print(row, flush=True)


if __name__ == '__main__':
    main()
