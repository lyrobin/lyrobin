"""Module for crons jobs."""

import datetime as dt
import uuid
import urllib.parse
import base64

from ai import gemini
from firebase_admin import firestore, storage  # type: ignore
from firebase_functions import logger, scheduler_fn
from firebase_functions.options import Timezone, MemoryOption
from google.cloud.firestore import DocumentSnapshot, FieldFilter, Or, Client  # type: ignore
from legislature import models

_TZ = Timezone("Asia/Taipei")

_MAX_PREDICTIONS = 1
_MAX_BATCH_SUMMARY_QUERY_SIZE = 1000
_MAX_BATCH_TRANSCRIPT_QUERY_SIZE = 150


@scheduler_fn.on_schedule(
    schedule="0 16 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=3600,
)
def update_meeting_files_embeddings(_: scheduler_fn.ScheduledEvent):
    try:
        _update_meeting_files_embeddings()
    except Exception as e:
        logger.error(f"Fail to update meeting files embeddings, {e}")
        raise RuntimeError("Fail to update meeting files embeddings.") from e


def _update_meeting_files_embeddings():
    db = firestore.client()

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = db.collection_group(models.FILE_COLLECT).where(
            filter=FieldFilter(
                "embedding_updated_at",
                "<=",
                dt.datetime(1, 1, 1, tzinfo=dt.timezone.utc),
            )
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(200).stream())

    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        files = [models.MeetingFile.from_dict(doc.to_dict()) for doc in docs]
        contents = [
            file.full_text if len(file.full_text) < 8000 else file.ai_summary
            for file in files
        ]
        queries = [
            gemini.EmbeddingQuery(doc.reference.path, content)
            for doc, content, file in zip(docs, contents, files)
            if content and file.embedding_updated_at <= file.last_update_time
        ]
        uid = uuid.uuid4().hex
        gemini.GeminiBatchEmbeddingJob.create(uid).submit(queries)


@scheduler_fn.on_schedule(
    schedule="0 20 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=3600,
)
def update_proceeding_attachment_embedding(_):
    try:
        _update_proceeding_attachment_embedding()
    except Exception as e:
        logger.error(f"Fail to update proceeding attachment embeddings, {e}")
        raise RuntimeError(
            f"Fail to update proceeding attachment embeddings, {e}"
        ) from e


def _update_proceeding_attachment_embedding():
    db = firestore.client()

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = db.collection_group(models.ATTACH_COLLECT).where(
            filter=FieldFilter(
                "embedding_updated_at",
                "<=",
                dt.datetime(1, 1, 1, tzinfo=dt.timezone.utc),
            )
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(200).stream())

    last_doc = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        attachments = [models.Attachment.from_dict(doc.to_dict()) for doc in docs]
        contents = [
            (
                attachment.full_text
                if len(attachment.full_text) < 8000
                else attachment.ai_summary
            )
            for attachment in attachments
        ]
        queries = [
            gemini.EmbeddingQuery(doc.reference.path, content)
            for doc, content, attachment in zip(docs, contents, attachments)
            if content
            and attachment.embedding_updated_at <= attachment.last_update_time
        ]
        uid = uuid.uuid4().hex
        # TODO: create a better job name for debugging
        gemini.GeminiBatchEmbeddingJob.create(uid).submit(queries)


def running_predictions(db: Client) -> int:
    query = Or(
        filters=[
            FieldFilter("job_type", "==", "transcript"),
            FieldFilter("job_type", "==", "summary"),
        ]
    )
    return int(
        db.collection(gemini.GEMINI_COLLECTION)
        .where(filter=query)
        .where(filter=FieldFilter("finished", "==", False))
        .count()
        .get()[0][0]
        .value
    )


@scheduler_fn.on_schedule(
    schedule="0 16 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=1800,
)
def update_meeting_files_summaries(_):
    try:
        _update_meeting_files_summaries()
    except Exception as e:
        logger.error(f"Fail to update meeting files summaries, {e}")
        raise RuntimeError("Fail to update meeting files summaries.") from e


def _update_meeting_files_summaries():
    db = firestore.client()

    if (count := running_predictions(db)) >= _MAX_PREDICTIONS:
        logger.warn(
            f"Exceed max running predictions ({count}), skip update meeting summary."
        )
        return

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = db.collection_group(models.FILE_COLLECT).where(
            filter=FieldFilter(
                "ai_summarized_at",
                "<=",
                dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc),
            )
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(200).stream())

    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchDocumentSummaryJob(uid)
    query_size = 0
    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        files = [models.MeetingFile.from_dict(doc.to_dict()) for doc in docs]
        queries = [
            gemini.DocumentSummaryQuery(doc.reference.path, file.full_text)
            for doc, file in zip(docs, files)
            if file.full_text
        ]
        job.write_queries(queries)
        query_size += len(queries)
        if query_size >= _MAX_BATCH_SUMMARY_QUERY_SIZE:
            break
    job.submit()


@scheduler_fn.on_schedule(
    schedule="0 18 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=1800,
)
def update_attachments_summaries(_):
    try:
        _update_attachments_summaries()
    except Exception as e:
        logger.error(f"Fail to update attachments summaries, {e}")
        raise RuntimeError("Fail to update attachments summaries.") from e


def _update_attachments_summaries():
    db = firestore.client()

    if (count := running_predictions(db)) >= _MAX_PREDICTIONS:
        logger.warn(
            f"Exceed max running predictions ({count}), skip update attachment summary."
        )
        return

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = db.collection_group(models.ATTACH_COLLECT).where(
            filter=FieldFilter(
                "ai_summarized_at",
                "<=",
                dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc),
            )
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(200).stream())

    query_size = 0
    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchDocumentSummaryJob(uid)
    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        files = [models.Attachment.from_dict(doc.to_dict()) for doc in docs]
        queries = [
            gemini.DocumentSummaryQuery(doc.reference.path, file.full_text)
            for doc, file in zip(docs, files)
            if file.full_text
        ]
        job.write_queries(queries)
        query_size += len(queries)
        if query_size >= _MAX_BATCH_SUMMARY_QUERY_SIZE:
            break
    job.submit()


@scheduler_fn.on_schedule(
    schedule="0 20 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=1800,
)
def update_speeches_summaries(_):
    try:
        _update_speeches_summaries()
    except Exception as e:
        logger.error(f"Fail to update speeches summaries, {e}")
        raise RuntimeError("Fail to update speeches summaries.") from e


def _update_speeches_summaries():
    db = firestore.client()

    if (count := running_predictions(db)) >= _MAX_PREDICTIONS:
        logger.warn(
            f"Exceed max running predictions ({count}), skip update speech summary."
        )
        return

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = (
            db.collection_group(models.SPEECH_COLLECT)
            .where(
                filter=FieldFilter(
                    "ai_summarized_at",
                    "<=",
                    dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc),
                )
            )
            .where(filter=FieldFilter("has_transcript", "==", True))
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(200).stream())

    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchDocumentSummaryJob(uid)
    query_size = 0
    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        videos = [models.Video.from_dict(doc.to_dict()) for doc in docs]
        queries = [
            gemini.TranscriptSummaryQuery(
                doc.reference.path, video.transcript, video.member
            )
            for doc, video in zip(docs, videos)
            if video.transcript
        ]
        job.write_queries(queries)
        query_size += len(queries)
        if query_size >= _MAX_BATCH_SUMMARY_QUERY_SIZE:
            break
    job.submit()


@scheduler_fn.on_schedule(
    schedule="0 16 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=1800,
)
def update_speech_transcripts(_):
    try:
        _update_speech_transcripts()
    except Exception as e:
        logger.error(f"Fail to update videos transcripts, {e}")
        raise RuntimeError("Fail to update videos transcripts.") from e


def _update_speech_transcripts():
    db = firestore.client()

    if (count := running_predictions(db)) >= _MAX_PREDICTIONS:
        logger.warn(
            f"Exceed max running predictions ({count}), skip update speech transcription."
        )
        return

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = db.collection_group(models.SPEECH_COLLECT).where(
            filter=FieldFilter(
                "transcript_updated_at",
                "<=",
                dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc),
            )
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(50).stream())

    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchAudioTranscriptJob(uid)
    bucket = storage.bucket()
    query_size = 0
    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        videos = [models.Video.from_dict(doc.to_dict()) for doc in docs]
        queries = []
        for video, doc in zip(videos, docs):
            if not video.audios:
                continue
            audio = video.audios[0]
            url = urllib.parse.urlparse(audio)
            blob = bucket.get_blob(url.path.strip("/"))
            if not blob.exists():
                logger.warn(f"{blob.name} doesn't exist")
                continue
            if blob.size > 19.5 * 1024**2:  # 19.5 MB
                logger.warn(f"{blob.name} is too large")
                continue
            queries.append(
                gemini.AudioTranscriptQuery(
                    doc.reference.path, base64.b64encode(blob.download_as_bytes())
                )
            )
        job.write_queries(queries)
        query_size += len(queries)
        if query_size >= _MAX_BATCH_TRANSCRIPT_QUERY_SIZE:
            break
        while queries:
            del queries[0]
    job.submit()
