"""Module for subscribers that handle cloud event outside of firebase functions."""

import dataclasses
import datetime as dt
import itertools
import json

import functions_framework
import opencc  # type: ignore
import pytz  # type: ignore
from ai import gemini
from ai import models as aimodels
from cloudevents.http.event import CloudEvent
from firebase_admin import firestore  # type: ignore
from firebase_functions import firestore_fn, logger, storage_fn
from firebase_functions.options import MemoryOption, SupportedRegion
from legislature import models
from utils import tasks

_EAST_TZ = pytz.timezone("US/Eastern")
_REGION = SupportedRegion.ASIA_EAST1


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
def on_receive_bigquery_batch_updates(event: CloudEvent):
    resource: str | None = event.get("resourcename")
    if not resource:
        raise ValueError(f"Need bigquery event, got {event}.")
    tokens = resource.strip("/").split("/")
    attributes = {k: v for k, v in zip(tokens[0::2], tokens[1::2])}
    table = attributes["tables"]
    logger.info(f"Received bigquery event for {table}")
    if table.startswith(
        f"prediction-{gemini.PredictionJob.HASHTAGS_TOPIC_SUMMARY}-destination"
    ):
        _process_hashtags_topic_summary_job(event)
    else:
        logger.warn(f"No handler found for {table}")


def _process_hashtags_topic_summary_job(event: CloudEvent):
    db = firestore.client()
    job = gemini.GeminiHashTagsTopicSummaryJob.from_bq_event(event)
    for rows in itertools.batched(job.list_results(), 50):
        batch = db.batch()
        for row in rows:
            ref = db.document(row.doc_path)
            doc = ref.get()
            if not doc.exists:
                logger.warn(f"No document found for {row.doc_path}")
                continue
            m = aimodels.Topic.from_dict(doc.to_dict())
            m.summarized = True
            m.title = row.title
            m.summary = row.summary
            batch.update(ref, m.to_dict())
        batch.commit()
    job.mark_as_done()


@functions_framework.cloud_event
def on_receive_bigquery_batch_document_summary(event: CloudEvent):
    db = firestore.client()
    cc = opencc.OpenCC("s2tw")
    job = gemini.GeminiBatchDocumentSummaryJob.from_bq_event(event)
    for rows in itertools.batched(job.list_results(), 50):
        batch = db.batch()
        for row in rows:
            ref = db.document(row.doc_path)
            doc = ref.get()
            if not doc.exists:
                logger.warn(f"No document found for {row.doc_path}")
                continue
            document = models.FireStoreDocument.from_dict(doc.to_dict())
            document.ai_summarized = True
            document.ai_summary = cc.convert(row.text)
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
        video.has_transcript = row.transcript != ""
        batch.update(ref, video.asdict())
    batch.commit()
    job.mark_as_done()


@functions_framework.cloud_event
def on_receive_bigquery_batch_speeches_summary(event: CloudEvent):
    db = firestore.client()
    job = gemini.GeminiBatchSpeechesSummaryJob.from_bq_event(event)
    batch = db.batch()
    for row in job.list_results():
        ref = db.document(row.doc_path)
        doc = ref.get()
        if not doc.exists:
            logger.warn(f"No document found for {row.doc_path}")
            continue
        member = models.Legislator.from_dict(doc.to_dict())
        remarks = [dataclasses.asdict(r) for r in row.remarks]
        member.ai_summary = json.dumps(remarks)
        member.ai_summarized = True
        member.ai_summarized_at = dt.datetime.now(tz=_EAST_TZ)
        batch.update(ref, member.asdict())
    batch.commit()
    job.mark_as_done()


@functions_framework.cloud_event
def on_receive_bigquery_batch_hashtags_summary(event: CloudEvent):
    db = firestore.client()
    job = gemini.GeminiHashTagsSummaryJob.from_bq_event(event)
    for rows in itertools.batched(job.list_results(), 50):
        batch = db.batch()
        for row in rows:
            ref = db.document(row.doc_path)
            doc = ref.get()
            if not doc.exists:
                logger.warn(f"No document found for {row.doc_path}")
                continue
            m = models.FireStoreDocument.from_dict(doc.to_dict())
            m.has_hash_tags = bool(row.tags)
            m.hash_tags = row.tags
            m.hash_tags_summarized_at = dt.datetime.now(tz=_EAST_TZ)
            batch.update(ref, m.asdict())
        batch.commit()
    job.mark_as_done()


# TODO: Remove this function once we have a proper handler for news reports.
@firestore_fn.on_document_created(
    document="news_reports/{documentId}",
    region=_REGION,
    memory=MemoryOption.MB_512,
)
def on_news_report_created(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
):
    doc_id = event.params["documentId"]
    logger.warn(f"Received news report {doc_id}, but no handler is implemented.")
    # q = tasks.CloudRunQueue("generateNewsReport", region=gemini.GEMINI_REGION)
    # q.run(doc=doc_id)
