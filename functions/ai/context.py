"""Provide context for RAG."""

from typing import IO, Any, Generator

from firebase_admin import firestore  # type: ignore
from google.cloud.firestore import DocumentSnapshot, FieldFilter, Query  # type: ignore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from legislature import models
from wiki import models as wiki_models


def attach_legislators_background(f: IO[str], terms: list[int]):
    assert len(terms) < 30, "Can't query more than 30 terms."
    _terms = [str(t) for t in terms]
    db = firestore.client()
    collection = db.collection(models.MEMBER_COLLECT)
    rows: Generator[DocumentSnapshot, Any, None]
    if _terms:
        rows = collection.where(
            filter=FieldFilter("terms", "array_contains_any", _terms)
        ).stream()
    else:
        rows = collection.stream()
    lines: list[str] = []
    for row in rows:
        m = models.Legislator.from_dict(row.to_dict())
        lines.extend(
            [
                f"## {m.name}\n\n",
                "- 屆別: " + ",".join(str(t) for t in m.terms) + "\n"
                f"- 黨籍: {m.party}\n",
                f"- 學歷: {m.degree}\n",
                f"- 性別: {m.sex}\n",
                f"- 選區: {m.area}\n",
                "\n",
            ]
        )
    if not lines:
        return
    f.write("# 立委名單\n\n")
    f.writelines(lines)
    f.write("\n\n")


def attach_directors_background(f: IO[str], vectors: list[Vector], limit: int = 20):
    db = firestore.client()
    collection = db.collection(wiki_models.DIRECTORS_COLLECTION)

    docs: list[wiki_models.DirectorsDocument] = []
    q: Query
    for v in vectors:
        q = collection.find_nearest(
            "embedding",
            query_vector=v,
            distance_measure=DistanceMeasure.EUCLIDEAN,
            limit=limit,
        )
        docs.extend(
            wiki_models.DirectorsDocument.from_dict(row.to_dict()) for row in q.stream()
        )

    seen: set[str] = set()
    f.write("# 行政機關首長\n\n")
    for doc in docs:
        if doc.organization in seen:
            continue
        seen.add(doc.organization)
        f.write(f"## {doc.organization}\n\n")
        f.write(doc.markdown + "\n\n")
