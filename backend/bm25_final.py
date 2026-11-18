"""Reproducible final BM25F expert search: build, validate, search.

Run from backend/ after installing Whoosh and placing the original baseline index.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from bm25_baseline import INDEX_PATH, search_documents
from bm25_discounted import course_group_key
from bm25_stopwords import build as build_stopword_index
from bm25_stemming import validate as validate_indexes

FINAL_INDEX_PATH = Path(__file__).resolve().parent / 'whoosh_bm25_final_index'
DOCUMENT_LIMIT = 100
DOCUMENT_WEIGHTS = {'paper': 1.0, 'project': 3.0, 'course': 1.0}


def aggregate(documents, people, limit=10):
    """Discount repeated offerings of a course harmonically, then rank researchers."""
    scores = defaultdict(float)
    counts = defaultdict(int)
    groups = defaultdict(lambda: defaultdict(list))
    for doc in documents:
        score = float(doc['bm25_score'])
        if not math.isfinite(score) or score < 0:
            raise ValueError(f"Invalid BM25 score for {doc['document_id']}")
        kind = doc['document_type']
        if kind not in DOCUMENT_WEIGHTS:
            raise ValueError(f'Unexpected document type: {kind}')
        for uid in set(doc['researcher_uuids']):
            if uid not in people:
                continue
            counts[uid] += 1
            if kind == 'course':
                key = course_group_key(doc.get('title') or '', doc['document_id'])
                groups[uid][key].append((score, doc['document_id']))
            else:
                scores[uid] += score * DOCUMENT_WEIGHTS[kind]
    for uid, titles in groups.items():
        for offerings in titles.values():
            for position, (score, _) in enumerate(sorted(offerings, key=lambda x: (-x[0], x[1])), 1):
                scores[uid] += score * DOCUMENT_WEIGHTS['course'] / position
    ranked = sorted(counts, key=lambda uid: (-scores[uid], uid))[:limit]
    return [{**people[uid], 'score': scores[uid], 'matched_document_count': counts[uid]}
            for uid in ranked]


def search_people(query: str, limit: int = 10):
    """Search researchers using the final tuned BM25F configuration."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    people_path = FINAL_INDEX_PATH / "people.json"

    if not people_path.exists():
        raise FileNotFoundError(
            "Final BM25 index not found. "
            "Run: python bm25_final.py build"
        )

    people = json.loads(
        people_path.read_text(encoding="utf-8")
    )

    documents = search_documents(
        query,
        limit=DOCUMENT_LIMIT,
        path=FINAL_INDEX_PATH,
    )

    return aggregate(documents, people, limit=limit)



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('build', 'validate'):
        p = sub.add_parser(name)
        p.add_argument('--source', type=Path, default=INDEX_PATH,
                       help='Existing original baseline index with stored payloads and people.json')
        p.add_argument('--target', type=Path, default=FINAL_INDEX_PATH)
    p = sub.add_parser('search')
    p.add_argument('query')
    p.add_argument('--index', type=Path, default=FINAL_INDEX_PATH)
    p.add_argument('--top-k', type=int, default=10)
    args = parser.parse_args()
    if args.command == 'build':
        result = build_stopword_index(source=args.source, target=args.target)
        print(json.dumps(result, indent=2))
    elif args.command == 'validate':
        result = validate_indexes(source=args.source, target=args.target)
        print(json.dumps(result, indent=2))
    else:
        if args.top_k < 1:
            parser.error('--top-k must be positive')
        if not (args.index / 'people.json').exists():
            parser.error(f'Missing index or people.json: {args.index}')
        people = json.loads((args.index / 'people.json').read_text(encoding='utf-8'))
        documents = search_documents(args.query, limit=DOCUMENT_LIMIT, path=args.index)
        print(json.dumps({'query': args.query, 'document_limit': DOCUMENT_LIMIT,
                          'retrieved_documents': len(documents),
                          'weights': DOCUMENT_WEIGHTS,
                          'results': aggregate(documents, people, args.top_k)},
                         ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
