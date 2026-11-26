# Final BM25 Search

This is our tuned BM25F expert search implementation.

## Local setup

Use the Docker setup below if you run the backend with Docker Compose. For a
local build, make sure the original index exists at `backend/whoosh_bm25_index/`
and includes `people.json`. From `backend/`, install the dependencies in your
active Python environment and build the final index:

```bash
python -m pip install -r requirements.txt
python bm25_final.py build
python bm25_final.py validate
```

This creates `backend/whoosh_bm25_final_index/`.

## Docker Compose setup

The root `docker-compose.yaml` stores the indexes in the named Docker volume
`backend-data`, mounted at `/app/whoosh` inside the backend container. Docker
Desktop manages this volume separately from the `backend/` folder on your Mac.
The files survive container recreation.

| Index | Path inside the container |
| --- | --- |
| Baseline | `/app/whoosh/whoosh_bm25_index/` |
| Final | `/app/whoosh/whoosh_bm25_final_index/` |

Compose sets `BM25_INDEX_ROOT=/app/whoosh`.
Without this environment variable, local builds still use the `backend/` folder.
Existing indexes elsewhere are not moved automatically.

The backend image installs Whoosh from `requirements.txt`. Run these commands
from `backend/`. The `-f ../docker-compose.yaml` option selects the root Compose
file, which defines the backend build context and index volume.
Build the baseline only if the Docker volume does not already contain it.

```bash
docker compose -f ../docker-compose.yaml up -d --build backend
docker compose -f ../docker-compose.yaml exec backend python bm25_baseline.py build
docker compose -f ../docker-compose.yaml exec backend python bm25_final.py build
docker compose -f ../docker-compose.yaml exec backend python bm25_final.py validate
```

The baseline build requires database connectivity. Do not use `docker compose down -v`
if you want to retain the indexes: that command removes the named volumes.

## Search

Researcher name matches are ranked first. You can search by full name
(`toine bogers`) or by a single name word (`toine` or `bogers`). Matching ignores
capitalization and extra whitespace. Topic queries use BM25 document ranking.

With the Compose backend running, test the final index from `backend/`:

```bash
docker compose -f ../docker-compose.yaml exec backend python bm25_final.py search "machine learning"
```

The command prints a ranked list of researchers. To test the running API on
the default host port, open the [example search](http://127.0.0.1:8000/search?q=machine%20learning&limit=3)
in your browser to see up to three results as JSON.

If you built the index locally, run this from `backend/`:

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
