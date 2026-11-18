"""Build a Whoosh index with stemming + English stopword removal.

Run from backend/:
    python -u bm25_stopwords.py build
    python bm25_stopwords.py validate
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from whoosh import index
from whoosh.analysis import StemmingAnalyzer, STOP_WORDS
from whoosh.fields import ID, STORED, TEXT, Schema

from bm25_stemming import STEM_INDEX_PATH, records, validate


STOP_INDEX_PATH = (
    Path(__file__).resolve().parent
    / "whoosh_bm25_stemming_stopwords_index"
)


def make_stopword_schema():
    analyzer = StemmingAnalyzer(stoplist=STOP_WORDS)

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


def build(source=STEM_INDEX_PATH, target=STOP_INDEX_PATH):
    source = Path(source).resolve()
    target = Path(target).resolve()

    if source == target:
        raise ValueError("Source and target indexes must differ")

    if not (source / "people.json").exists():
        raise FileNotFoundError(
            f"Missing people.json in {source}"
        )

    documents = records(source)

    if not documents:
        raise ValueError("Source index is empty")

    ids = [d["document_id"] for d in documents]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate document IDs")

    print(
        f"Building stopword index from {len(documents)} documents",
        flush=True,
    )

    if target.exists():
        shutil.rmtree(target)

    target.mkdir(parents=True)

    ix = index.create_in(
        target,
        schema=make_stopword_schema(),
    )

    with ix.writer(limitmb=128) as writer:
        for i, d in enumerate(documents, start=1):
            writer.add_document(
                document_id=d["document_id"],
                document_type=d["document_type"],
                title=d.get("title") or "",
                subtitle=d.get("subtitle") or "",
                abstract=d.get("abstract") or "",
                description=d.get("description") or "",
                programme=d.get("programme") or "",
                payload=json.dumps(
                    d,
                    ensure_ascii=False,
                    default=str,
                ),
            )

            if i % 1000 == 0:
                print(
                    f"Indexed {i}/{len(documents)}",
                    flush=True,
                )

    shutil.copyfile(
        source / "people.json",
        target / "people.json",
    )

    return validate(source, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "command",
        choices=["build", "validate"],
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=STEM_INDEX_PATH,
    )

    parser.add_argument(
        "--target",
        type=Path,
        default=STOP_INDEX_PATH,
    )

    args = parser.parse_args()

    if args.command == "build":
        result = build(args.source, args.target)
    else:
        result = validate(args.source, args.target)

    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()