"""Module for subscribers that handle cloud event outside of firebase functions."""

import datetime as dt

from firebase_admin import firestore  # type: ignore
from firebase_functions import storage_fn, logger
from firebase_functions.options import MemoryOption
from ai import gemini
from legislature import models


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
