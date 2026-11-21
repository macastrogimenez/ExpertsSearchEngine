# Final BM25 Search

This is our tuned BM25F expert search implementation.

## Setup

1. Make sure the original index exists at `backend/whoosh_bm25_index/` (including `people.json`). **The final index is built from this original index**, so you need to create or obtain it first.
2. From the `backend/` folder, run:

```bash
python bm25_final.py build
python bm25_final.py validate
```

This creates `backend/whoosh_bm25_final_index/`.

## Search

From `backend/`:

```bash
python bm25_final.py search "machine learning"
```

## Final configuration

- Search fields: title, subtitle, abstract, description, programme
- Stemming and stopword removal enabled
- Equal field weights
- BM25F retrieves the top 100 documents
- Researcher ranking: Discounted CombSUM
- Document weights: **papers 1, projects 3, courses 1**
- Returns the top 10 researchers by default

The document weights and aggregation are applied **when searching**, not stored in the index.

## GitHub

Commit `bm25_final.py`, this README, and the supporting Python scripts. **Do not commit generated Whoosh indexes.** Add these paths to the root `.gitignore`:

```gitignore
backend/whoosh_bm25_final_index/
```

The final configuration achieved **0.3658 nDCG@10**, compared with **0.2676** for the original baseline on our 452-query tuning set.

## API Endpoints

All API endpoints for the final tuned BM25 search are defined in `main_bm25.py`.

The `/search` endpoint uses the final optimized BM25 implementation from `bm25_final.py`. Other endpoints provide researcher, paper, project, and course information.
