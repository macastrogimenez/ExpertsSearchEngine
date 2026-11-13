"""Researcher search and Whoosh index management for the prod schema."""
import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from dbconfig import DB_CONFIG
from whoosh import index

def load_experts():
    """Load one document per researcher without multiplying join rows."""
    with psycopg.connect(**DB_CONFIG, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT uuid, firstname, lastname, email FROM prod.person')
            people = {str(r['uuid']): {
                'uuid': str(r['uuid']),
                'name': ' '.join(filter(None, [r['firstname'], r['lastname']])),
                'email': r['email'] or '',
                'paper_titles': [], 'paper_abstracts': [],
                'courses': [], 'projects': [], 'project_descriptions': []
            } for r in cur.fetchall()}

            cur.execute('''
                SELECT DISTINCT pc.person_uuid, p.uuid, p.title, p.abstract
                FROM prod.paper_contributors pc
                JOIN prod.paper p ON p.uuid = pc.paper_uuid
            ''')
            for r in cur.fetchall():
                person = people.get(str(r['person_uuid']))
                if person:
                    if r['title']: person['paper_titles'].append(r['title'])
                    if r['abstract']: person['paper_abstracts'].append(r['abstract'])

            cur.execute('''
                SELECT DISTINCT cc.person_uuid, c.id, c.title
                FROM prod.course_contributor cc
                JOIN prod.course c ON c.id = cc.course_id
            ''')
            for r in cur.fetchall():
                person = people.get(str(r['person_uuid']))
                if person and r['title']:
                    person['courses'].append(r['title'])

            cur.execute('''
                SELECT DISTINCT pp.person_uuid, p.uuid, p.title, p.description
                FROM prod.project_participants pp
                JOIN prod.project p ON p.uuid = pp.project_uuid
            ''')
            for r in cur.fetchall():
                person = people.get(str(r['person_uuid']))
                if person:
                    if r['title']: person['projects'].append(r['title'])
                    if r['description']: person['project_descriptions'].append(r['description'])
    return people

from whoosh.fields import Schema, ID, TEXT, STORED

INDEX_DIR = Path(os.getenv('WHOOSH_INDEX_DIR', str(Path(__file__).resolve().parent / 'whoosh_index')))


def build_index():
    people = load_experts()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    schema = Schema(
        row_id=ID(stored=True, unique=True),
        person_name=TEXT(stored=True),
        paper_titles=TEXT(), paper_abstracts=TEXT(),
        courses=TEXT(), projects=TEXT(), project_descriptions=TEXT(),
        payload=STORED,
    )
    ix = index.create_in(str(INDEX_DIR), schema)
    writer = ix.writer(limitmb=256)
    try:
        for p in people.values():
            writer.add_document(
                row_id=p['uuid'], person_name=p['name'],
                paper_titles=' '.join(p['paper_titles']),
                paper_abstracts=' '.join(p['paper_abstracts']),
                courses=' '.join(p['courses']),
                projects=' '.join(p['projects']),
                project_descriptions=' '.join(p['project_descriptions']),
                payload=p,
            )
        writer.commit()
    except Exception:
        writer.cancel()
        raise
    print(f'Indexed {len(people)} researchers in {INDEX_DIR}')



import re
from typing import Any
from whoosh.qparser import QueryParser, MultifieldParser, OrGroup
from whoosh.scoring import BM25F

MAX_RESULTS = 15
FIELDS = ['person_name', 'paper_titles', 'projects', 'project_descriptions', 'paper_abstracts', 'courses']


def normalize_name(text: str) -> str:
    return ' '.join(text.lower().strip().split())


def tokenize_query(text: str) -> list[str]:
    return [token for token in re.findall(r'\w+', text.lower()) if len(token) > 1]


def detect_query_type(query_text: str, searcher, ix) -> str:
    words = query_text.strip().split()
    if len(words) == 1:
        return 'single_token'
    if len(words) != 2:
        return 'mixed'
    parser = QueryParser('person_name', schema=ix.schema, group=OrGroup.factory(0.9))
    hits = searcher.search(parser.parse(query_text), limit=5)
    return 'full_name' if any(normalize_name(h['person_name']) == normalize_name(query_text) for h in hits) else 'mixed'


def get_field_boosts(query_type: str) -> dict[str, float]:
    return {
        'person_name': 5.0 if query_type == 'full_name' else 1.5 if query_type == 'single_token' else 1.8,
        'paper_titles': 3.0, 'projects': 2.4,
        'project_descriptions': 2.0, 'paper_abstracts': 1.6, 'courses': 1.1,
    }


def score_item_against_query(item: str, query_text: str) -> int:
    tokens = tokenize_query(query_text)
    if not item or not tokens:
        return 0
    return sum(t in set(tokenize_query(item)) for t in tokens) + (3 if query_text.lower() in item.lower() else 0)


def rank_relevant_items(items: list[str], query_text: str, limit: int = 5) -> list[str]:
    scored = [(score_item_against_query(item, query_text), item) for item in items]
    return [item for score, item in sorted(scored, key=lambda x: x[0], reverse=True) if score > 0][:limit]


def get_relevant_evidence(row: dict[str, Any], query_text: str) -> dict[str, list[str]]:
    return {field: rank_relevant_items(row[field], query_text) for field in
            ('paper_titles', 'paper_abstracts', 'courses', 'projects', 'project_descriptions')}


def get_name_match_bonus(query_text: str, name: str, query_type: str) -> float:
    q, n = normalize_name(query_text), normalize_name(name)
    if not q or not n:
        return 0.0
    if q == n:
        return 40.0 if query_type == 'full_name' else 20.0
    overlap = len(set(q.split()) & set(n.split()))
    if query_type == 'full_name':
        return 25.0 if overlap == 2 else 8.0 if overlap == 1 else 0.0
    if query_type == 'single_token' and q in n.split():
        return 8.0
    return 0.0


def search_people(query_text: str, limit: int = MAX_RESULTS) -> dict[str, Any]:
    limit = max(1, min(limit, MAX_RESULTS))
    query_text = query_text.strip()
    if not query_text:
        return {'query': query_text, 'query_type': 'empty', 'count': 0, 'results': []}
    if not index.exists_in(str(INDEX_DIR)):
        build_index()

    ix = index.open_dir(str(INDEX_DIR))
    with ix.searcher(weighting=BM25F()) as searcher:
        query_type = detect_query_type(query_text, searcher, ix)
        parser = MultifieldParser(FIELDS, schema=ix.schema,
                                  fieldboosts=get_field_boosts(query_type),
                                  group=OrGroup.factory(0.9))
        hits = searcher.search(parser.parse(query_text), limit=limit * 10)
        ranked = []
        for hit in hits:
            row = hit['payload']
            evidence = get_relevant_evidence(row, query_text)
            if query_type != 'full_name' and not any(evidence.values()):
                continue
            bonus = get_name_match_bonus(query_text, row['name'], query_type)
            score = hit.score + bonus
            if query_type == 'full_name' and bonus > 0:
                score += 5.0
            if query_type != 'full_name' and any(evidence.values()):
                score += 2.0
            ranked.append({
                'uuid': row['uuid'], 'name': row['name'], 'email': row['email'],
                'papers': row['paper_titles'][:10], 'projects': row['projects'][:10],
                'courses': row['courses'][:10],
                'all_papers': row['paper_titles'], 'all_projects': row['projects'],
                'all_courses': row['courses'],
                'paper_count': len(row['paper_titles']),
                'project_count': len(row['projects']),
                'course_count': len(row['courses']),
                'matched_evidence': evidence, 'raw_score': round(score, 4),
            })
    ranked.sort(key=lambda r: r['raw_score'], reverse=True)
    final = ranked[:limit]
    if final:
        low, high = min(r['raw_score'] for r in final), max(r['raw_score'] for r in final)
        for r in final:
            r['score'] = round((r['raw_score'] - low) / (high - low), 4) if high != low else 1.0
    return {'query': query_text, 'query_type': query_type, 'count': len(final), 'results': final}


if __name__ == "__main__":
    build_index()
