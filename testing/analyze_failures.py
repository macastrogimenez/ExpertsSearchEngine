"""Failure analysis for known-positive experts in the frozen ITU BM25F index.

From backend/:
  python ../testing/analyze_failures.py --queries ../testing/test_queries_final.csv \
    --output ../testing/bm25_failure_analysis

Uses the existing Whoosh index; does not rebuild or change it.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / 'backend'
sys.path.insert(0, str(BACKEND_DIR))

from bm25_baseline import INDEX_PATH, combsum, search_documents
from bm25_discounted import discounted_combsum
from whoosh import index


def normalize_name(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value or '').casefold()).strip()


def save_csv(path, rows, columns):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def plot_results(rows, output):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib unavailable; CSVs saved, skipping plots')
        return
    plot_dir = output / 'plots'
    plot_dir.mkdir(exist_ok=True)
    types = sorted({r['query_type'] for r in rows})
    statuses = ['name_not_matched', 'not_in_index', 'no_document_in_top_100', 'ranking_failure', 'in_top_10']
    labels = ['Name not matched', 'No indexed evidence', 'No docs in top 100', 'Ranking failure', 'Found in top 10']
    counts = {typ: Counter(r['status_at_100_discounted'] for r in rows if r['query_type'] == typ) for typ in types}
    fig, ax = plt.subplots(figsize=(10, 5))
    bottoms = [0] * len(types)
    for status, label in zip(statuses, labels):
        vals = [counts[t][status] for t in types]
        ax.bar(types, vals, bottom=bottoms, label=label)
        bottoms = [a + b for a, b in zip(bottoms, vals)]
    ax.set_ylabel('Expected-expert instances')
    ax.set_title('Why expected experts are missing (discounted CombSUM, depth 100)')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / 'failure_types_by_query_type.png', dpi=180)
    plt.close(fig)

    depths = sorted(int(k.removeprefix('rank_combsum_')) for k in rows[0] if k.startswith('rank_combsum_'))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for method in ('combsum', 'discounted'):
        vals = [sum(r[f'rank_{method}_{d}'] != '' and int(r[f'rank_{method}_{d}']) <= 10 for r in rows) / len(rows) for d in depths]
        ax.plot(depths, vals, marker='o', label=method)
    ax.set_xlabel('BM25F document retrieval depth')
    ax.set_ylabel('Fraction of known-positive experts in top 10')
    ax.set_title('Known-positive top-10 coverage vs retrieval depth')
    ax.set_ylim(0, 1)
    ax.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / 'top10_coverage_by_depth.png', dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queries', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('bm25_failure_analysis'))
    parser.add_argument('--index', type=Path, default=INDEX_PATH)
    parser.add_argument('--depths', type=int, nargs='+', default=[100, 250, 500])
    args = parser.parse_args()
    depths = sorted(set(args.depths) | {100})
    if min(depths) < 10:
        parser.error('All retrieval depths must be >= 10')
    args.output.mkdir(parents=True, exist_ok=True)

    with args.queries.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required = {'query', 'query_type', 'expected_experts'}
        if not required.issubset(reader.fieldnames or []):
            parser.error(f'Missing query columns: {required - set(reader.fieldnames or [])}')
        queries = list(reader)

    print(f'Loaded {len(queries)} query rows; retrieval depths: {depths}', flush=True)
    people = json.loads((args.index / 'people.json').read_text(encoding='utf-8'))
    name_to_ids = defaultdict(set)
    for uid, person in people.items():
        name_to_ids[normalize_name(person['name'])].add(uid)

    # Check actual index associations, not merely researcher presence in people.json.
    ix = index.open_dir(args.index)
    indexed_counts = Counter()
    with ix.searcher() as searcher:
        for stored in searcher.all_stored_fields():
            payload = json.loads(stored['payload'])
            for uid in set(payload['researcher_uuids']):
                indexed_counts[uid] += 1

    print(f'Indexed evidence counted for {len(indexed_counts)} researchers. Starting query analysis...', flush=True)
    cache = {}
    rows = []
    for qid, query_row in enumerate(queries, start=1):
        if qid == 1 or qid % 10 == 0 or qid == len(queries):
            print(f'Processing query {qid}/{len(queries)} (unique searches: {len(cache)})', flush=True)
        query = (query_row['query'] or '').strip()
        if not query:
            continue
        if query not in cache:
            retrieved = search_documents(query, limit=max(depths), path=args.index)
            by_depth = {}
            for depth in depths:
                docs = retrieved[:depth]
                uids = Counter(uid for d in docs for uid in set(d['researcher_uuids']))
                ranked_a = combsum(docs, people, limit=len(people))
                ranked_b = discounted_combsum(docs, people, limit=len(people))
                by_depth[depth] = (uids,
                                   {r['uuid']: i for i, r in enumerate(ranked_a, 1)},
                                   {r['uuid']: i for i, r in enumerate(ranked_b, 1)}, len(docs))
            cache[query] = by_depth
        for raw_name in (query_row['expected_experts'] or '').split(';'):
            expected_name = normalize_name(raw_name)
            if not expected_name:
                continue
            ids = name_to_ids.get(expected_name, set())
            row = {'query_id': qid, 'query': query, 'query_type': query_row['query_type'],
                   'expected_expert': raw_name.strip(), 'matched_researcher_uuids': ';'.join(sorted(ids)),
                   'indexed_document_count': sum(indexed_counts[uid] for uid in ids)}
            for depth in depths:
                counts, baseline_ranks, discounted_ranks, n_docs = cache[query][depth]
                row[f'retrieved_document_count_{depth}'] = n_docs
                row[f'expert_document_hits_{depth}'] = sum(counts[uid] for uid in ids)
                for method, ranks in [('combsum', baseline_ranks), ('discounted', discounted_ranks)]:
                    possible = [ranks[uid] for uid in ids if uid in ranks]
                    row[f'rank_{method}_{depth}'] = min(possible) if possible else ''
                    if not ids:
                        status = 'name_not_matched'
                    elif not any(indexed_counts[uid] for uid in ids):
                        status = 'not_in_index'
                    elif not possible:
                        status = 'no_document_in_top_100' if depth == 100 else 'no_document_retrieved'
                    elif min(possible) > 10:
                        status = 'ranking_failure'
                    else:
                        status = 'in_top_10'
                    row[f'status_at_{depth}_{method}'] = status
            rows.append(row)

    columns = list(rows[0]) if rows else []
    save_csv(args.output / 'expert_failure_details.csv', rows, columns)
    summary = []
    for typ in ['ALL', *sorted({r['query_type'] for r in rows})]:
        subset = rows if typ == 'ALL' else [r for r in rows if r['query_type'] == typ]
        for depth in depths:
            for method in ('combsum', 'discounted'):
                c = Counter(r[f'status_at_{depth}_{method}'] for r in subset)
                for status, count in sorted(c.items()):
                    summary.append({'query_type': typ, 'depth': depth, 'method': method,
                                    'status': status, 'count': count, 'total': len(subset),
                                    'fraction': count / len(subset) if subset else 0})
    save_csv(args.output / 'failure_summary.csv', summary,
             ['query_type', 'depth', 'method', 'status', 'count', 'total', 'fraction'])
    if rows:
        plot_results(rows, args.output)
    print(json.dumps({'queries': len(queries), 'unique_queries': len(cache),
                      'expected_expert_instances': len(rows),
                      'output': str(args.output),
                      'depth_100_discounted': dict(Counter(r['status_at_100_discounted'] for r in rows))}, indent=2))


if __name__ == '__main__':
    main()
