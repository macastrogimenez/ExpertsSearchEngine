import psycopg
from typing import Any
from dbconfig import DB_CONFIG


def get_person_data(person_uuid: str) -> list[dict[str, Any]]:
    with psycopg.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.firstname,
                    p.lastname,
                    p.email,
                    p.jobtitle
                FROM prod.person p
                WHERE p.uuid = %s
                """,
                (person_uuid,),
            )

            rows = cur.fetchall()

    return [
        {
            "first_name": row[0] or "",
            "last_name": row[1] or "",
            "email": row[2] or "",
            "job_title": row[3] or "",
        }
        for row in rows
    ]