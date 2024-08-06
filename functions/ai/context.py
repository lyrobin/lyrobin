"""Provide context for RAG."""

from typing import IO, Generator, Any

from legislature import models

from firebase_admin import firestore  # type: ignore
from google.cloud.firestore import FieldFilter, DocumentSnapshot  # type: ignore


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
