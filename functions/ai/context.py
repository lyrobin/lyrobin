"""Provide context for RAG."""

from typing import IO, Any, Generator

from firebase_admin import firestore  # type: ignore
from google.cloud.firestore import DocumentSnapshot, FieldFilter, Query  # type: ignore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from legislature import models
from params import EMBEDDING_MODEL
from vertexai.language_models import (
    TextEmbeddingInput,  # type: ignore
    TextEmbeddingModel,
)
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


def attach_directors_background(f: IO[str], query: str, limit: int = 20):
    db = firestore.client()
    collection = db.collection(wiki_models.DIRECTORS_COLLECTION)

    q: Query
    if query:
        model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL.value)
        embeddings = model.get_embeddings(
            [TextEmbeddingInput(query, "RETRIEVAL_QUERY")],
            output_dimensionality=wiki_models.EMBEDDING_SIZE,
        )
        q = collection.find_nearest(
            "embedding",
            query_vector=Vector(embeddings[0].values),
            distance_measure=DistanceMeasure.EUCLIDEAN,
            limit=limit,
        )
    else:
        q = collection.limit(limit)

    rows = q.stream()
    f.write("# 行政機關首長\n\n")
    for row in rows:
        m = wiki_models.DirectorsDocument.from_dict(row.to_dict())
        f.write(f"## {m.organization}\n\n")
        f.write(m.markdown + "\n\n")
