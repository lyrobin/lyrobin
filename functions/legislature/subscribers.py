"""Module for subscribers that handle cloud event outside of firebase functions."""

import datetime as dt

import functions_framework
import opencc  # type: ignore
import pytz  # type: ignore
from ai import gemini
from cloudevents.http.event import CloudEvent
from firebase_admin import firestore  # type: ignore
from firebase_functions import logger, storage_fn
from firebase_functions.options import MemoryOption
from legislature import models

_EAST_TZ = pytz.timezone("US/Eastern")


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
def on_receive_bigquery_batch_document_summary(event: CloudEvent):
    db = firestore.client()
    batch = db.batch()
    cc = opencc.OpenCC("s2tw")
    job = gemini.GeminiBatchDocumentSummaryJob.from_bq_event(event)
    for row in job.list_results():
        ref = db.document(row.doc_path)
        doc = ref.get()
        if not doc.exists:
            logger.warn(f"No document found for {row.doc_path}")
            continue
        document = models.FireStoreDocument.from_dict(doc.to_dict())
        document.ai_summarized = True
        document.ai_summarized = cc.convert(row.text)
        document.ai_summarized_at = dt.datetime.now(tz=_EAST_TZ)
        batch.update(ref, document.asdict())
    batch.commit()
    job.mark_as_done()


@functions_framework.cloud_event
def on_receive_bigquery_batch_audio_transcripts(event: CloudEvent):
    db = firestore.client()
    job = gemini.GeminiBatchAudioTranscriptJob.from_bq_event(event)
    cc = opencc.OpenCC("s2tw")
    batch = db.batch()
    for row in job.list_results():
        ref = db.document(row.doc_path)
        doc = ref.get()
        if not doc.exists:
            logger.warn(f"No document found for {row.doc_path}")
            continue
        video = models.Video.from_dict(doc.to_dict())
        video.transcript = cc.convert(row.transcript)
        video.transcript_updated_at = dt.datetime.now(tz=_EAST_TZ)
        batch.update(ref, video.asdict())
    batch.commit()
    job.mark_as_done()
