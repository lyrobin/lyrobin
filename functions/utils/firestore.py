"""Utility functions for Firestore operations."""

from typing import Iterable
from google.cloud import firestore as cloud_firestore  # type: ignore


def iterate_all_documents(
    query: cloud_firestore.Query,
) -> Iterable[cloud_firestore.DocumentSnapshot]:
    """Iterate over a query."""
    pointer = None
    while True:
        if pointer:
            docs = query.start_after(pointer).stream()
        else:
            docs = query.stream()
        pointer = None
        for doc in docs:
            pointer = doc
            yield doc
        if not pointer:
            break
