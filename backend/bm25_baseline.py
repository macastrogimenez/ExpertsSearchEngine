"""Document-centric ITU expert retrieval: Whoosh BM25F -> CombSUM.

Run:
    python bm25_baseline.py build
    python bm25_baseline.py validate
    python bm25_baseline.py search 'machine learning for healthcare' --limit 10

Requires dbconfig.py exporting DB_CONFIG for psycopg.connect(**DB_CONFIG).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from whoosh import index
from whoosh.analysis import StandardAnalyzer
from whoosh.fields import ID, STORED, TEXT, Schema
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.scoring import BM25F

from dbconfig import DB_CONFIG

INDEX_PATH = Path(__file__).resolve().parent / 'whoosh_bm25_index'
SEARCH_FIELDS = ('title', 'subtitle', 'abstract', 'description', 'programme')
DEFAULT_DOCUMENT_LIMIT = 100


def json_safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    return value


def fetch_all(conn: psycopg.Connection, sql: str) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def load_data() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Fetch documents independently from relationship tables to avoid duplicate indexing."""
    with psycopg.connect(**DB_CONFIG) as conn:
        people_rows = fetch_all(conn, '''
            SELECT uuid, orcid, firstname, lastname, email, jobtitle
            FROM prod.person
        ''')
        paper_rows = fetch_all(conn, '''
            SELECT uuid, doi, year, type, title, subtitle, abstract, university, file_url
            FROM prod.paper
        ''')
        project_rows = fetch_all(conn, '''
            SELECT uuid, title, description, period_start_date, period_end_date, portal_url
            FROM prod.project
        ''')
        course_rows = fetch_all(conn, '''
            SELECT id, semester, title, language, abstract, description, programme
            FROM prod.course
        ''')
        paper_links = fetch_all(conn, '''
            SELECT paper_uuid, person_uuid, role FROM prod.paper_contributors
        ''')
        project_links = fetch_all(conn, '''
            SELECT project_uuid, person_uuid, role FROM prod.project_participants
        ''')
        course_links = fetch_all(conn, '''
            SELECT course_id, person_uuid FROM prod.course_contributor
        ''')
        project_paper_links = fetch_all(conn, '''
            SELECT project_uuid, paper_uuid FROM prod.project_papers
        ''')

    people = {}
    for row in people_rows:
        uid = str(row['uuid'])
        people[uid] = {
            'uuid': uid,
            'orcid': row['orcid'] or '',
            'first_name': row['firstname'] or '',
            'last_name': row['lastname'] or '',
            'name': ' '.join(filter(None, [row['firstname'], row['lastname']])),
            'email': row['email'] or '',
            'job_title': row['jobtitle'] or '',
        }

    associations: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    roles: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for kind, rows, key in (
        ('paper', paper_links, 'paper_uuid'),
        ('project', project_links, 'project_uuid'),
        ('course', course_links, 'course_id'),
    ):
        for row in rows:
            doc_id = f'{kind}:{row[key]}'
            person_id = str(row['person_uuid'])
            if person_id not in people:
                continue  # Don't return candidates missing from prod.person.
            associations[kind][doc_id].add(person_id)
            if row.get('role'):
                roles[kind][doc_id][person_id].add(str(row['role']))

    project_papers: dict[str, set[str]] = defaultdict(set)
    for row in project_paper_links:
        project_papers[f"project:{row['project_uuid']}"].add(str(row['paper_uuid']))

    documents = []
    for kind, rows, key in (
        ('paper', paper_rows, 'uuid'),
        ('project', project_rows, 'uuid'),
        ('course', course_rows, 'id'),
    ):
        for row in rows:
            doc_id = f'{kind}:{row[key]}'
            # Documents with no linked ITU researcher cannot contribute to expert ranking.
            # Keep them indexed for consistent corpus statistics and document retrieval.
            metadata = json_safe(dict(row))
            if kind == 'project':
                metadata['related_paper_uuids'] = sorted(project_papers[doc_id])
            documents.append({
                'document_id': doc_id,
                'document_type': kind,
                'title': row.get('title') or '',
                'subtitle': row.get('subtitle') or '',
                'abstract': row.get('abstract') or '',
                'description': row.get('description') or '',
                'programme': row.get('programme') or '',
                'researcher_uuids': sorted(associations[kind][doc_id]),
                'contributor_roles': {
                    uid: sorted(role_set)
                    for uid, role_set in roles[kind][doc_id].items()
                },
                'metadata': metadata,
            })
    return people, documents


def make_schema() -> Schema:
    analyzer = StandardAnalyzer(stoplist=None)  # Fixed baseline: no stopword removal, no stemming.
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



def build_index(path: Path = INDEX_PATH) -> dict[str, Any]:
    people, documents = load_data()

    # Keep only documents connected to at least one known researcher
    valid_people = {str(uuid) for uuid in people}

    documents = [
        d for d in documents
        if any(
            str(uuid) in valid_people
            for uuid in d["researcher_uuids"]
        )
    ]

    # Ensure all document IDs are unique
    doc_ids = [d["document_id"] for d in documents]
    if len(doc_ids) != len(set(doc_ids)):
        raise ValueError("Duplicate document IDs in database extraction.")

    # Rebuild the Whoosh index
    if path.exists():
        shutil.rmtree(path)

    path.mkdir(parents=True)

    ix = index.create_in(path, schema=make_schema())

    with ix.writer(limitmb=128) as writer:
        for d in documents:
            # Keep only valid researcher associations
            d["researcher_uuids"] = [
                str(uuid)
                for uuid in d["researcher_uuids"]
                if str(uuid) in valid_people
            ]

            writer.add_document(
                document_id=d["document_id"],
                document_type=d["document_type"],
                title=d["title"],
                subtitle=d["subtitle"],
                abstract=d["abstract"],
                description=d["description"],
                programme=d["programme"],
                payload=json.dumps(
                    json_safe(d),
                    ensure_ascii=False,
                    default=str
                ),
            )

    # Save researcher metadata
    (path / "people.json").write_text(
        json.dumps(json_safe(people), ensure_ascii=False, default=str),
        encoding="utf-8"
    )

    counts = {
        kind: sum(d["document_type"] == kind for d in documents)
        for kind in ("paper", "project", "course")
    }

    return {
        "researchers": len(people),
        "documents": len(documents),
        "by_type": counts,
        "unassociated_documents": 0
    }


def search_documents(query: str, limit: int = DEFAULT_DOCUMENT_LIMIT,
                     path: Path = INDEX_PATH) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    if limit < 1:
        raise ValueError('limit must be >= 1')
    ix = index.open_dir(path)
    parser = MultifieldParser(SEARCH_FIELDS, schema=ix.schema, group=OrGroup)
    parsed = parser.parse(query)
    with ix.searcher(weighting=BM25F(B=0.75, K1=1.2)) as searcher:
        hits = searcher.search(parsed, limit=limit)
        results = []
        for hit in hits:
            doc = json.loads(hit['payload'])
            doc['bm25_score'] = float(hit.score)
            results.append(doc)
        return results


def combsum(documents: list[dict[str, Any]], people: dict[str, dict[str, Any]],
            limit: int = 10) -> list[dict[str, Any]]:
    scores: dict[str, float] = defaultdict(float)
    evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in documents:
        score = float(doc['bm25_score'])
        if not math.isfinite(score) or score < 0:
            raise ValueError(f"Invalid BM25 score for {doc['document_id']}: {score}")
        for uid in set(doc['researcher_uuids']):
            if uid not in people:
                continue
            scores[uid] += score
            evidence[uid].append({
                'document_id': doc['document_id'],
                'document_type': doc['document_type'],
                'title': doc['title'],
                'bm25_score': score,
            })
    ordered = sorted(scores, key=lambda uid: (-scores[uid], uid))
    return [
        {**people[uid], 'score': scores[uid], 'matched_document_count': len(evidence[uid]),
         'supporting_documents': sorted(evidence[uid], key=lambda d: (-d['bm25_score'], d['document_id']))}
        for uid in ordered[:limit]
    ]


def search_experts(query: str, limit: int = 10, document_limit: int = DEFAULT_DOCUMENT_LIMIT,
                   path: Path = INDEX_PATH) -> dict[str, Any]:
    if limit < 1:
        raise ValueError('limit must be >= 1')
    people = json.loads((path / 'people.json').read_text(encoding='utf-8'))
    docs = search_documents(query, limit=document_limit, path=path)
    return {'query': query, 'aggregation': 'CombSUM', 'document_limit': document_limit,
            'retrieved_document_count': len(docs), 'results': combsum(docs, people, limit=limit)}


def validate_index(path: Path = INDEX_PATH) -> dict[str, Any]:
    ix = index.open_dir(path)
    people = json.loads((path / 'people.json').read_text(encoding='utf-8'))
    with ix.searcher() as searcher:
        stored = list(searcher.all_stored_fields())
    ids = [doc['document_id'] for doc in stored]
    if len(ids) != len(set(ids)):
        raise AssertionError('Index has duplicate document IDs')
    invalid = []
    counts = defaultdict(int)
    for entry in stored:
        payload = json.loads(entry['payload'])
        counts[payload['document_type']] += 1
        if any(uid not in people for uid in payload['researcher_uuids']):
            invalid.append(payload['document_id'])
    if invalid:
        raise AssertionError(f'Unknown researcher associations: {invalid[:10]}')
    return {'indexed_documents': len(stored), 'by_type': dict(counts),
            'unique_document_ids': True, 'associations_valid': True,
            'researchers': len(people)}


def main() -> None:
    parser = argparse.ArgumentParser(description='ITU document-centric Whoosh BM25F baseline')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('build')
    sub.add_parser('validate')
    search = sub.add_parser('search')
    search.add_argument('query')
    search.add_argument('--limit', type=int, default=10)
    search.add_argument('--document-limit', type=int, default=DEFAULT_DOCUMENT_LIMIT)
    docs = sub.add_parser('documents')
    docs.add_argument('query')
    docs.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    if args.command == 'build':
        output = build_index()
    elif args.command == 'validate':
        output = validate_index()
    elif args.command == 'documents':
        output = search_documents(args.query, args.limit)
    else:
        output = search_experts(args.query, args.limit, args.document_limit)
    print(json.dumps(json_safe(output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
