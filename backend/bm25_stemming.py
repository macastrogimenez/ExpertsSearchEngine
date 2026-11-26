"""Build and validate a stemming-only Whoosh index from the frozen baseline index.

From backend/:
    python bm25_stemming.py build
    python bm25_stemming.py validate

Does not query PostgreSQL or modify the baseline index.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, STORED, TEXT, Schema

from bm25_baseline import INDEX_PATH, INDEX_ROOT

STEM_INDEX_PATH = INDEX_ROOT / 'whoosh_bm25_stemming_index'
FIELDS = ('title', 'subtitle', 'abstract', 'description', 'programme')


def make_stemming_schema():
    # Disable stopword removal to isolate stemming as the experimental variable.
    analyzer = StemmingAnalyzer(stoplist=None)
    return Schema(
        document_id=ID(stored=True, unique=True),
        document_type=ID(stored=True),
        title=TEXT(stored=True, analyzer=analyzer),
        subtitle=TEXT(stored=False, analyzer=analyzer),
        abstract=TEXT(stored=False, analyzer=analyzer),
        description=TEXT(stored=False, analyzer=analyzer),
        programme=TEXT(stored=False, analyzer=analyzer),
        payload=STORED,
    )


def records(path):
    ix = index.open_dir(path)
    with ix.searcher() as searcher:
        return [json.loads(item['payload']) for item in searcher.all_stored_fields()]


def signature(docs):
    return {d['document_id']: (d['document_type'], tuple(sorted(d['researcher_uuids']))) for d in docs}


def build(source=INDEX_PATH, target=STEM_INDEX_PATH):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise ValueError('Source and target indexes must differ')
    if not (source / 'people.json').exists():
        raise FileNotFoundError(f'Missing baseline people.json: {source}')
    docs = records(source)
    if not docs:
        raise ValueError('Baseline index is empty')
    ids = [d['document_id'] for d in docs]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate document IDs in baseline index')
    print(f'Loaded {len(docs)} documents from baseline index', flush=True)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    ix = index.create_in(target, schema=make_stemming_schema())
    with ix.writer(limitmb=128) as writer:
        for i, d in enumerate(docs, 1):
            writer.add_document(
                document_id=d['document_id'],
                document_type=d['document_type'],
                title=d.get('title') or '',
                subtitle=d.get('subtitle') or '',
                abstract=d.get('abstract') or '',
                description=d.get('description') or '',
                programme=d.get('programme') or '',
                payload=json.dumps(d, ensure_ascii=False, default=str),
            )
            if i % 1000 == 0:
                print(f'Indexed {i}/{len(docs)}', flush=True)
    shutil.copyfile(source / 'people.json', target / 'people.json')
    return validate(source, target)


def validate(source=INDEX_PATH, target=STEM_INDEX_PATH):
    source, target = Path(source), Path(target)
    a, b = records(source), records(target)
    if signature(a) != signature(b):
        raise AssertionError('Document IDs/types/researcher associations differ between indexes')
    if {d['document_id']: d for d in a} != {d['document_id']: d for d in b}:
        raise AssertionError('Document payloads differ between indexes')
    if json.loads((source / 'people.json').read_text(encoding='utf-8')) != json.loads((target / 'people.json').read_text(encoding='utf-8')):
        raise AssertionError('Researcher metadata differs between indexes')
    return {'validated': True, 'documents': len(b),
            'by_type': dict(Counter(d['document_type'] for d in b)),
            'researcher_metadata_identical': True, 'payloads_identical': True,
            'stemming_index': str(target)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['build', 'validate'])
    p.add_argument('--source', type=Path, default=INDEX_PATH)
    p.add_argument('--target', type=Path, default=STEM_INDEX_PATH)
    args = p.parse_args()
    result = build(args.source, args.target) if args.command == 'build' else validate(args.source, args.target)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
