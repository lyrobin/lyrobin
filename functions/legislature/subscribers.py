"""Module for subscribers that handle cloud event outside of firebase functions."""

import datetime as dt
import json
from typing import Any

import firebase_admin  # type: ignore
from firebase_admin import firestore  # type: ignore
from firebase_functions import storage_fn, logger
from firebase_functions.options import MemoryOption
from ai import gemini
from legislature import models
import functions_framework
from cloudevents.http.event import CloudEvent
from google.cloud import bigquery
from google.cloud.bigquery import table
import opencc  # type: ignore
import pytz # type: ignore

_EAST_TZ = pytz.timezone('US/Eastern')


@storage_fn.on_object_finalized(
    bucket=gemini.GEMINI_BUCKET,
    region=gemini.GEMINI_REGION,
    memory=MemoryOption.GB_1,
    max_instances=5,
    concurrency=5,
)
def on_default_bucket_object_finalized(
    event=storage_fn.CloudEvent[storage_fn.StorageObjectData],
):
    if (job := gemini.GeminiBatchEmbeddingJob.load(event.data.name)) is not None:
        _process_batch_embedding_job(job)
    else:
        logger.warn(f"No handler found for {event.data.name}")


def _process_batch_embedding_job(job: gemini.GeminiBatchEmbeddingJob):
    db = firestore.client()
    batch = db.batch()
    for result in job.results():
        ref = db.document(result.doc_path)
        doc = ref.get()
        if not doc.exists:
            logger.warn(f"No document found for {result.doc_path}")
            continue
        m = models.FireStoreDocument.from_dict(doc.to_dict())
        m.embedding_vector = result.embedding
        m.embedding_updated_at = dt.datetime.now(tz=models.MODEL_TIMEZONE)
        batch.update(ref, m.asdict())
    batch.commit()


@functions_framework.cloud_event
def on_receive_bigquery_batch_predictions(event: CloudEvent):
    app: firebase_admin.App = firebase_admin.get_app()
    resource: str | None = event.get("resourcename")
    if not resource:
        return
    tokens = resource.strip("/").split("/")
    attributes = {k: v for k, v in zip(tokens[0::2], tokens[1::2])}
    table_id = f"{attributes["projects"]}.{attributes["datasets"]}.{attributes["tables"]}"
    client = bigquery.Client(project=app.project_id)
    rows_iter = client.list_rows(table_id)

    db = firestore.client()
    batch = db.batch()
    cc = opencc.OpenCC("s2tw")
    row:table.Row
    for row in rows_iter:
        doc_path: str = row.get("doc_path")
        ref = db.document(doc_path)
        if not ref.get().exists:
            logger.warn(f"No document found for {doc_path}")
            continue
        doc = models.FireStoreDocument.from_dict(ref.get().to_dict())
        response:list[dict[str, Any]] = json.loads(row.get("response"))
        if len(response) != 1:
            logger.warn(f"Unsupported response for {doc_path}, {response}")
            continue
        parts = response[0].get("content", {}).get("parts", [])
        if not parts:
            logger.warn(f"No parts found for {doc_path}")
            continue
        text = parts[0].get("text", "")
        if not text:
            logger.warn(f"No text found for {doc_path}")
            continue
        doc.ai_summarized = True
        doc.ai_summary = cc.convert(text)
        doc.ai_summarized_at = dt.datetime.now(tz=_EAST_TZ)
        batch.update(ref, doc.asdict())
    batch.commit()
