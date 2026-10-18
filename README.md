# ExpertsSearchEngine

## Backend: Build and run docker container

```Bash
docker build -t experts-backend ./backend
docker run --rm -p 127.0.0.1:8000:8000 experts-backend
```

## Document-to-embedding processor

To run the embedding processor the .env file needs to be obtained and loaded to the current terminal session.

```Bash
cd embeddingProcessor/       
source env.sh
```

## Backend: Embedding model

This model turned our search documents into vectors, but it will also vectorise the user query.

The commands below mount the Ollama image and download the model into the running container:

```Bash
cd embeddingProcessor/       
docker compose up -d
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

/*
TODO: Continue from https://chatgpt.com/s/t_6ad53828a9008191bbf95ecfc19df6fd
    where it says: "The nomic-embed-text model is available directly through Ollama and is designed specifically for embedding generation."
    check if any docker related stuff should be included in gitignore

*/
