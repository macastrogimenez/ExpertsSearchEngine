# ExpertsSearchEngine

## Backend: Build and run docker container

```Bash
docker build -t experts-backend ./backend
docker run --rm -p 127.0.0.1:8000:8000 experts-backend
```

### Build Whoosh index

After running the above-mentioned commands this runs builds the Whoosh index locally in the
already running container.

```Bash
docker exec objective_jemison python /app/search.py
```
