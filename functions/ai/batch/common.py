"""Collect common batch functions for AI tasks."""

import datetime as dt
import io
import json

import ai
import gembatch  # type: ignore
from ai import context
from ai import embeddings as ai_embeddings
from firebase_admin import firestore  # type: ignore
from google.cloud import firestore_v1 as cloud_firestore
from google.cloud.firestore_v1 import vector as firestore_vector
from legislature import models
from utils import timeutil
from vertexai import generative_models as gm  # type: ignore

_MODEL = "publishers/google/models/gemini-1.5-flash-002"


def start_generate_hashtags(content: str, doc_path: str) -> None:
    """Generate hashtags from transcript."""
    gembatch.submit(
        {
            "contents": [{"role": "user", "parts": [{"text": content}]}],
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Please generate a short list of hashtags "
                            "that capture the essence of the following document. "
                            "PLease notice:\n"
                            "1. The list should be as short as possible\n"
                            "2. Do not create more than 10 tags.\n"
                            "3. Create tags in zh-TW."
                        )
                    }
                ]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "safetySettings": ai.NON_BLOCKING_SAFE_SETTINGS,
        },
        _MODEL,
        on_receive_hashtags,
        {
            "doc_path": doc_path,
        },
    )


def on_receive_hashtags(response: gm.GenerationResponse, doc_path: str = "") -> None:
    """Handle response from hashtag generation."""
    if not doc_path:
        raise ValueError("No document path provided.")
    if not response.text:
        raise ValueError("No hashtags generated.")
    db = firestore.client()
    ref = db.document(doc_path)
    if not ref.get().exists:
        raise ValueError(f"Document {doc_path} does not exist.")
    document = models.FireStoreDocument.from_dict(ref.get().to_dict())
    hashtags: list[str] = json.loads(response.text)
    if not isinstance(hashtags, list):
        raise ValueError("Hashtags must be a list.")
    document.hash_tags = [tag.strip("#") for tag in hashtags]
    document.hash_tags_summarized_at = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    document.has_hash_tags = True
    document.last_update_time = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    ref.update(document.asdict())


def start_generate_summary(
    ref: cloud_firestore.DocumentReference,
    content: str,
    created_time: dt.datetime | None = None,
) -> None:
    if created_time is None:
        created_time = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    term = timeutil.get_legislative_yuan_term(created_time)
    if not term:
        raise ValueError(f"No term found for {ref.path}.")

    vectors: list[firestore_vector.Vector] = []
    try:
        embeddings = models.get_embeddings(ref)
        vectors = [e.to_vector() for e in embeddings]
    except models.EmbeddingMismatchError:
        vectors = ai_embeddings.get_embedding_vectors_from_text(content)

    if not vectors:
        vectors = ai_embeddings.get_embedding_vectors_from_text(content)

    buf = io.StringIO()
    context.attach_directors_background(buf, vectors)
    context.attach_legislators_background(buf, [term])

    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": "請根據下述的內容，以繁體中文做出詳盡的人物及事件介紹。"
                        },
                        {"text": content},
                    ],
                }
            ],
            "systemInstruction": {"parts": [{"text": buf.getvalue()}]},
            "safetySettings": ai.NON_BLOCKING_SAFE_SETTINGS,
        },
        _MODEL,
        on_receive_summary,
        {
            "doc_path": ref.path,
        },
    )


def on_receive_summary(response: gm.GenerationResponse, doc_path: str = "") -> None:
    if not doc_path:
        raise ValueError("No document path provided.")
    if not response.text:
        raise ValueError("No summary generated.")
    db = firestore.client()
    ref = db.document(doc_path)
    if not ref.get().exists:
        raise ValueError(f"Document {doc_path} does not exist.")
    document = models.FireStoreDocument.from_dict(ref.get().to_dict())
    document.ai_summary = response.text
    document.ai_summarized_at = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    document.ai_summarized = True
    document.last_update_time = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    ref.update(document.asdict())
