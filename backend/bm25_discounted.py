"""Compare standard CombSUM with course-discounted CombSUM on the frozen BM25F index.

Usage:
    python bm25_discounted.py search "machine learning" --limit 10
    python bm25_discounted.py compare "machine learning" --limit 10
    python bm25_discounted.py search "machine learning" --limit 10 --document-limit 100
"""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from bm25_baseline import INDEX_PATH, DEFAULT_DOCUMENT_LIMIT, combsum, search_documents


def course_group_key(title: str, document_id: str) -> str:
    """Group identical course titles (case/whitespace/Unicode normalized).

    Missing titles are kept separate so unrelated untitled courses aren't merged.
    """
    normalized = unicodedata.normalize('NFKC', title or '').casefold()
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized if normalized else f'__untitled__:{document_id}'


def discounted_combsum(documents: list[dict[str, Any]],
                       people: dict[str, dict[str, Any]],
                       limit: int = 10) -> list[dict[str, Any]]:
    """Rank experts with harmonic discount across repeated course offerings.

    Within each researcher and normalized course title, sorted scores contribute
    s_1 + s_2/2 + s_3/3 + ... . Other document scores contribute in full.
    """
    if limit < 1:
        raise ValueError('limit must be >= 1')

    evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    course_groups: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    scores: dict[str, float] = defaultdict(float)

    for doc in documents:
        score = float(doc['bm25_score'])
        if not math.isfinite(score) or score < 0:
            raise ValueError(f"Invalid BM25 score for {doc['document_id']}: {score}")
        for uid in set(doc['researcher_uuids']):
            if uid not in people:
                continue
            entry = {
                'document_id': doc['document_id'],
                'document_type': doc['document_type'],
                'title': doc['title'],
                'bm25_score': score,
            }
            evidence[uid].append(entry)
            if doc['document_type'] == 'course':
                key = course_group_key(doc['title'], doc['document_id'])
                course_groups[uid][key].append(entry)
            else:
                scores[uid] += score

    for uid, groups in course_groups.items():
        for offerings in groups.values():
            offerings.sort(key=lambda d: (-d['bm25_score'], d['document_id']))
            for position, offering in enumerate(offerings, start=1):
                scores[uid] += offering['bm25_score'] / position

    ordered = sorted(evidence, key=lambda uid: (-scores[uid], uid))
    return [
        {
            **people[uid],
            'score': scores[uid],
            'matched_document_count': len(evidence[uid]),
            'distinct_course_count': len(course_groups[uid]),
            'supporting_documents': sorted(
                evidence[uid], key=lambda d: (-d['bm25_score'], d['document_id'])
            ),
        }
        for uid in ordered[:limit]
    ]


def run_search(query: str, limit: int = 10,
               document_limit: int = DEFAULT_DOCUMENT_LIMIT,
               path: Path = INDEX_PATH,
               compare: bool = False) -> dict[str, Any]:
    if limit < 1:
        raise ValueError('limit must be >= 1')
    people = json.loads((path / 'people.json').read_text(encoding='utf-8'))
    docs = search_documents(query, limit=document_limit, path=path)
    discounted = discounted_combsum(docs, people, limit=limit)
    result = {
        'query': query,
        'aggregation': 'DiscountedCombSUM',
        'document_limit': document_limit,
        'retrieved_document_count': len(docs),
        'results': discounted,
    }
    if compare:
        result['aggregation'] = 'comparison'
        result['baseline_results'] = combsum(docs, people, limit=limit)
        result['discounted_results'] = result.pop('results')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='BM25F course-discounted CombSUM experiment')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('search', 'compare'):
        command = sub.add_parser(name)
        command.add_argument('query')
        command.add_argument('--limit', type=int, default=10)
        command.add_argument('--document-limit', type=int, default=DEFAULT_DOCUMENT_LIMIT)
    args = parser.parse_args()
    result = run_search(args.query, limit=args.limit,
                        document_limit=args.document_limit,
                        compare=args.command == 'compare')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
