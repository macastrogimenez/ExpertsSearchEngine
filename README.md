# ExpertsSearchEngine

## Backend: Build and run docker container

```Bash
docker build -t experts-backend ./backend
docker run --rm -p 127.0.0.1:8000:8000 experts-backend
```

## Document-to-embedding processor

The processor is a batch job that reads PostgreSQL documents, generates embeddings
with Ollama, writes them to Milvus, and exits. Its Dockerfile builds the Gradle
application with Java 21 and copies the application and dependencies into a Java
21 runtime image. Integration tests are not run during the image build.

Run these commands from the repository root. First load the PostgreSQL settings
(`DB_HOST`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD`) from your local `env.sh`.
The script and `.env` files are excluded from the image build context.

### command to generate embedding DB

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

### command to run vector search app

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

## Backend: Semantic search

Test to check the semantic search is running:

```Bash
curl --get 'http://localhost:8080/semanticSearch' \
  --data-urlencode 'query=machine learning in agriculture' \
  --data-urlencode 'K=5' \
  --data-urlencode 'filter=paper'
```

## Backend: Embedding model

This model turned our search documents into vectors, but it will also vectorise the user query.

The commands below mount the Ollama image and download the model into the running container:

```Bash
docker compose up -d ollama
docker compose exec ollama ollama pull nomic-embed-text
```

Test to check the embedding model is running:

```Bash
curl http://localhost:11434/api/embed \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed-text",
    "input": "search_query: machine learning"
  }'
```

