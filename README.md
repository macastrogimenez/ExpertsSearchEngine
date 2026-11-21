# ExpertsSearchEngine

## 1. Backend: Python Backend and Whoosh BM25 engine

Build and run docker container

```Bash
docker build -t experts-backend ./backend
docker run --rm --name experts-backend -p 127.0.0.1:8000:8000 experts-backend
```

### Build Whoosh index

After running the above-mentioned commands this runs builds the Whoosh index locally in the
already running container.

```Bash
docker exec experts-backend python /app/search.py
```

## 2. Backend: Semantic Search Engine (and document-to-embedding service)

This Java application has two functions:

- Pulling relevant data, generating documents, vectorising them and storing them in Milvus.
- Serving as a Semantic Search Engine to the Python Backend.

### 2.1 Generating vector database

The processor is a batch job that reads PostgreSQL documents, generates embeddings
with Ollama, writes them to Milvus, and exits. Its Dockerfile builds the Gradle
application with Java 21 and copies the application and dependencies into a Java
21 runtime image. Integration tests are not run during the image build.

Run these commands from the repository root. First load the PostgreSQL settings
(`DB_HOST`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD`) from your local `env.sh`.
The script and `.env` files are excluded from the image build context.


```Bash
set -a
source embeddingProcessor/env.sh
set +a

docker compose build embedding-processor
docker compose -f milvus/docker-compose.yml up -d --wait
docker compose up -d ollama
docker compose exec ollama ollama pull nomic-embed-text
docker compose run --rm --build embedding-processor embeddingGen
```

### 2.2 Running semantic search engine

```Bash
set -a
source embeddingProcessor/env.sh
set +a

docker compose -f milvus/docker-compose.yml up -d --wait

docker compose up -d ollama
docker compose exec ollama ollama pull nomic-embed-text

docker compose up -d --build embedding-processor
```

Milvus runs in its existing separate Compose stack. On Docker Desktop, the
processor uses `http://host.docker.internal:19530` to reach Milvus through its
published port. Override `MILVUS_URL` and `MILVUS_TOKEN` if using another server.
Inside the processor container, `localhost` refers to the processor itself. If
PostgreSQL runs on your Mac, set `DB_HOST=host.docker.internal` before running it.

#### 2.2.1 Semantic Search API: Documentation

The app listens on port 8080 and exposes its semantic search engine through two endpoints:

##### GET /semanticSearch

Which takes two parameters:

- (String) query: user query.
- (int) K: number of results to be returned.
  
##### GET /semanticSearchFiltered

Which takes three parameters:

- (String) query: user query.
- (int) K: number of results to be returned.
- (String) filter: valid values are either 'paper', 'project' or 'course'

##### VectorSearchResult - response to API requests to either endpoint

Responses are a List of VectorSearchResult, which have the following structure:

```Java
public record VectorSearchResult(
        String documentType,
        String documentId,
        List<String> contributors,
        float score
) {}
```

#### 2.2.2 Testing semantic search

Run this test from any terminal to check the semantic search is running:

```Bash
curl --get 'http://localhost:8080/semanticSearch' \
  --data-urlencode 'query=machine learning in agriculture' \
  --data-urlencode 'K=5'
```

```Bash
curl --get 'http://localhost:8080/semanticSearchFiltered' \
  --data-urlencode 'query= ai in agriculture' \
  --data-urlencode 'K=5' \
  --data-urlencode 'filter=paper'
```

### 2.4 Starting and testing the embedding model (NOT NEEDED if you already run steps 2.1 and 2.2)

IMPORTANT: This is only add-on information to understand the model that is processing the text into embeddings, however,
it is NOT NECESSARY to run this separately, since the service will be initiated together with the rest of the containers 
and services that form part of the Semantic Search Engine.

This model turned our search documents into vectors, but it will also vectorise the user query.

The commands below mount the Ollama image and download the model into the running container:

```Bash
docker compose up -d ollama
docker compose exec ollama ollama pull nomic-embed-text
```

Run this test from any terminal to check the embedding model is running:

```Bash
curl http://localhost:11434/api/embed \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed-text",
    "input": "search_query: machine learning"
  }'
```
