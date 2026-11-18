
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bm25_final import search_people
from paper_url import get_papers_by_person
from projects import get_projects_by_person
from courses import get_courses_by_person
from persons import get_person_data

MAX_RESULTS = 100

app = FastAPI(
    title="Expert Search API - Tuned BM25",
    version="1.0.0",
    description="API for expert retrieval using optimized BM25F and PostgreSQL",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FileURLsRequest(BaseModel):
    papers: list[str]


@app.get("/")
def root():
    return {
        "message": "Tuned BM25 Expert Search API is running",
        "search_endpoint": "/search?q=machine%20learning&limit=10",
        "max_limit": MAX_RESULTS,
    }


@app.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=MAX_RESULTS),
):
    return search_people(q, limit=limit)


@app.get("/papersByPerson")
def papers_by_person(person_uuid: str):
    return {
        "person_uuid": person_uuid,
        "papers": get_papers_by_person(person_uuid),
    }


@app.get("/projectsByPerson")
def projects_by_person(person_uuid: str):
    return {
        "person_uuid": person_uuid,
        "projects": get_projects_by_person(person_uuid),
    }


@app.get("/coursesByPerson")
def courses_by_person(person_uuid: str):
    return {
        "person_uuid": person_uuid,
        "courses": get_courses_by_person(person_uuid),
    }


@app.get("/person")
def person(person_uuid: str):
    return {
        "person_uuid": person_uuid,
        "data": get_person_data(person_uuid),
    }
