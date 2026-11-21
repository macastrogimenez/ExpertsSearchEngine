"""Build no-stemming + stopwords index from frozen no-stemming/no-stopwords index.
Run from backend/: python bm25_standard_stopwords.py build
"""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from whoosh import index
from whoosh.analysis import StandardAnalyzer, STOP_WORDS
from whoosh.fields import ID, STORED, TEXT, Schema
from bm25_baseline import INDEX_PATH
from bm25_stemming import records, validate

STANDARD_STOP_INDEX_PATH = Path(__file__).resolve().parent / "whoosh_bm25_standard_stopwords_index"

def make_schema():
    analyzer = StandardAnalyzer(stoplist=STOP_WORDS)
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

def build(source=INDEX_PATH, target=STANDARD_STOP_INDEX_PATH):
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise ValueError("Source and target must differ")
    docs = records(source)
    if not docs:
        raise ValueError("Source index is empty")
    if len({d["document_id"] for d in docs}) != len(docs):
        raise ValueError("Duplicate document IDs")
    if not (source / "people.json").exists():
        raise FileNotFoundError(source / "people.json")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    ix = index.create_in(target, schema=make_schema())
    with ix.writer(limitmb=128) as writer:
        for i, d in enumerate(docs, 1):
            writer.add_document(
                document_id=d["document_id"], document_type=d["document_type"],
                title=d.get("title") or "", subtitle=d.get("subtitle") or "",
                abstract=d.get("abstract") or "", description=d.get("description") or "",
                programme=d.get("programme") or "",
                payload=json.dumps(d, ensure_ascii=False, default=str),
            )
            if i % 1000 == 0:
                print(f"Indexed {i}/{len(docs)}", flush=True)
    shutil.copyfile(source / "people.json", target / "people.json")
    return validate(source, target)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["build", "validate"])
    args = p.parse_args()
    result = build() if args.command == "build" else validate(INDEX_PATH, STANDARD_STOP_INDEX_PATH)
    print(json.dumps(result, indent=2))
