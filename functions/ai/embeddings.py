"""The module provides utils for embedding."""

import itertools

from params import EMBEDDING_MODEL, EMBEDDING_SIZE
from vertexai.language_models import (  # type: ignore
    TextEmbeddingInput,
    TextEmbeddingModel,
)
from google.cloud.firestore_v1.vector import Vector

_MAX_EMBEDDING_INPUT_SIZE = 2048


def get_embeddings_from_text(text: str) -> list[list[float]]:
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL.value)
    inputs = [
        TextEmbeddingInput(text[i : i + _MAX_EMBEDDING_INPUT_SIZE], "RETRIEVAL_QUERY")
        for i in range(0, len(text), _MAX_EMBEDDING_INPUT_SIZE)
    ]
    ret: list[list[float]] = []
    for batch in itertools.batched(inputs, 9):
        embeddings = model.get_embeddings(
            batch, output_dimensionality=EMBEDDING_SIZE.value
        )
        ret.extend(e.values for e in embeddings)
    return ret


def get_embedding_vectors_from_text(txt: str) -> list[Vector]:
    return [Vector(e) for e in get_embeddings_from_text(txt)]
