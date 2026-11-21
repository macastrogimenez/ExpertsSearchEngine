"""Evaluate frozen BM25F CombSUM against course-discounted CombSUM.

Run from backend/:
  python evaluate_bm25.py --queries ../testing/test_queries_final.csv --output ../testing/bm25_results

This uses expected_experts as incomplete positive labels, NOT exhaustive relevance judgments.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
import sys

# Add backend folder to Python's import path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from bm25_baseline import INDEX_PATH, combsum, search_documents
from bm25_discounted import discounted_combsum


def normalize_name(value: str) -> str:
    value = unicodedata.normalize('NFKC', value or '').casefold()
    return re.sub(r'\s+', ' ', value).strip()


def known_positive_metrics(results: list[dict], expected: set[str], k: int) -> dict:
    # Binary metrics against known positives; incomplete labels make these provisional.
    retrieved = [normalize_name(x['name']) for x in results[:k]]
    hits = [int(name in expected) for name in retrieved]
    rr = next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0.0)
    dcg = sum(hit / math.log2(i + 2) for i, hit in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(expected), k)))
    return {
        'known_recall_at_k': sum(hits) / len(expected) if expected else float('nan'),
        'known_mrr_at_k': rr,
        'known_ndcg_at_k': dcg / ideal if ideal else float('nan'),
        'known_hits_at_k': sum(hits),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--queries', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path('bm25_results'))
    p.add_argument('--index', type=Path, default=INDEX_PATH)
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--document-limit', type=int, default=100)
    args = p.parse_args()
    if args.limit < 1 or args.document_limit < 1:
        p.error('--limit and --document-limit must be positive')
    args.output.mkdir(parents=True, exist_ok=True)
    with args.queries.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        required = {'query', 'query_type', 'expected_experts'}
        if not required.issubset(reader.fieldnames or []):
            p.error(f'CSV requires columns {sorted(required)}')
        queries = list(reader)
    people = json.loads((args.index / 'people.json').read_text(encoding='utf-8'))
    ranking_rows, metric_rows, comparison_rows, expected_rank_rows = [], [], [], []
    cache = {}
    for qid, row in enumerate(queries, 1):
        query = row['query'].strip()
        expected = {normalize_name(s) for s in row['expected_experts'].split(';') if s.strip()}
        if not query:
            continue
        # Identical queries share one retrieval, including repeated strings in the CSV.
        if query not in cache:
            docs = search_documents(query, limit=args.document_limit, path=args.index)
            cache[query] = (
                len(docs),
                combsum(docs, people, limit=args.limit),
                discounted_combsum(docs, people, limit=args.limit),
            )
        n_docs, baseline, discounted = cache[query]
        top_sets = {}
        for method, ranked in [('combsum', baseline), ('discounted', discounted)]:
            top_sets[method] = {x['uuid'] for x in ranked}
            m = known_positive_metrics(ranked, expected, args.limit)
            metric_rows.append({'query_id': qid, 'query': query, 'query_type': row['query_type'],
                                'method': method, 'expected_expert_count': len(expected),
                                'retrieved_document_count': n_docs, **m})
            for rank, expert in enumerate(ranked, 1):
                docs = expert['supporting_documents']
                ranking_rows.append({
                    'query_id': qid, 'query': query, 'query_type': row['query_type'],
                    'method': method, 'rank': rank, 'researcher_uuid': expert['uuid'],
                    'researcher_name': expert['name'], 'score': expert['score'],
                    'known_positive': int(normalize_name(expert['name']) in expected),
                    'matched_document_count': expert['matched_document_count'],
                    'matched_course_count': sum(d['document_type'] == 'course' for d in docs),
                    'matched_paper_count': sum(d['document_type'] == 'paper' for d in docs),
                    'matched_project_count': sum(d['document_type'] == 'project' for d in docs),
                })
        baseline_positions = {normalize_name(x['name']): i for i, x in enumerate(baseline, 1)}
        discounted_positions = {normalize_name(x['name']): i for i, x in enumerate(discounted, 1)}
        for expected_name in sorted(expected):
            baseline_rank = baseline_positions.get(expected_name)
            discounted_rank = discounted_positions.get(expected_name)
            expected_rank_rows.append({
                'query_id': qid, 'query': query, 'query_type': row['query_type'],
                'expected_expert': expected_name,
                'combsum_rank': baseline_rank if baseline_rank is not None else 'not_in_top_k',
                'discounted_rank': discounted_rank if discounted_rank is not None else 'not_in_top_k',
                'combsum_found': int(baseline_rank is not None),
                'discounted_found': int(discounted_rank is not None),
                'rank_improvement': baseline_rank - discounted_rank
                    if baseline_rank is not None and discounted_rank is not None else '',
            })
        a, b = top_sets['combsum'], top_sets['discounted']
        comparison_rows.append({
            'query_id': qid, 'query': query, 'query_type': row['query_type'],
            'top_k_overlap_count': len(a & b),
            'top_k_jaccard': len(a & b) / len(a | b) if (a | b) else 1.0,
            'same_first_result': int(bool(baseline and discounted) and baseline[0]['uuid'] == discounted[0]['uuid']),
            'retrieved_document_count': n_docs,
        })
        if qid % 50 == 0:
            print(f'Processed {qid}/{len(queries)} queries')

    def write_csv(name: str, rows: list[dict]) -> None:
        if not rows:
            return
        with (args.output / name).open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    write_csv('rankings.csv', ranking_rows)
    write_csv('metrics.csv', metric_rows)
    write_csv('comparison.csv', comparison_rows)
    write_csv('expected_expert_ranks.csv', expected_rank_rows)
    metadata = {'query_count': len(queries), 'unique_query_count': len(cache),
                'limit': args.limit, 'document_limit': args.document_limit,
                'index': str(args.index), 'evaluation_note': 'Known positives only; incomplete labels'}
    (args.output / 'run_config.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(args.output), **metadata}, indent=2))


if __name__ == '__main__':
    main()
