"""Module for crons jobs."""

import base64
import datetime as dt
import io
import urllib.parse
import uuid
import requests
import dataclasses

from ai import context, gemini
import firebase_admin  # type: ignore
from firebase_admin import firestore, storage  # type: ignore
from firebase_functions import logger, scheduler_fn
from firebase_functions.options import MemoryOption, Timezone, SupportedRegion
from google.cloud.firestore import DocumentSnapshot  # type: ignore
from google.cloud.firestore import Client, FieldFilter, Increment, Query
from legislature import models
from utils import tasks
import utils

_TZ = Timezone("Asia/Taipei")

_MAX_BATCH_SUMMARY_QUERY_SIZE = 200
_MAX_BATCH_TRANSCRIPT_QUERY_SIZE = 150
_MAX_ATTEMPTS = 2


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


def running_jobs(db: Client, caller: str) -> int:
    return int(
        db.collection(gemini.GEMINI_COLLECTION)
        .where(filter=FieldFilter("caller", "==", caller))
        .where(filter=FieldFilter("finished", "==", False))
        .count()
        .get()[0][0]
        .value
    )


def increment_attempts(db: Client, docs: list[str], field: str):
    """Increment the number of attempts for the given documents AI job."""
    batch = db.batch()
    for doc in docs:
        ref = db.document(doc)
        batch.update(ref, {field: Increment(1)})
    batch.commit()


@scheduler_fn.on_schedule(
    schedule="*/30 00-02,21-23 * * *",
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
    if running_jobs(db, "meeting_files_summaries"):
        logger.warn("Still have running jobs, skip update meeting files summaries.")
        return

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = (
            db.collection_group(models.FILE_COLLECT)
            .where(
                filter=FieldFilter(
                    "ai_summarized_at",
                    "<=",
                    dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc),
                )
            )
            .where(filter=FieldFilter("ai_summary_attempts", "<", _MAX_ATTEMPTS))
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(200).stream())

    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchDocumentSummaryJob(uid).set_caller(
        "meeting_files_summaries"
    )
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
        if not queries:
            continue
        _attach_legislator_context_to_summary_queries(db, queries)
        _attach_director_context_to_summary_queries(db, queries)
        increment_attempts(db, [q.doc_path for q in queries], "ai_summary_attempts")
        job.write_queries(queries)
        query_size += len(queries)
        if query_size >= _MAX_BATCH_SUMMARY_QUERY_SIZE:
            break
    if query_size <= 0:
        logger.warn("No queries to submit")
        return
    job.submit()


@scheduler_fn.on_schedule(
    schedule="*/30 00-02,21-23 * * *",
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

    if running_jobs(db, "attachments_summaries"):
        logger.warn("Still have running jobs, skip update attachments summaries.")
        return

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = (
            db.collection_group(models.ATTACH_COLLECT)
            .where(
                filter=FieldFilter(
                    "ai_summarized_at",
                    "<=",
                    dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc),
                )
            )
            .where(filter=FieldFilter("ai_summary_attempts", "<", _MAX_ATTEMPTS))
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(200).stream())

    query_size = 0
    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchDocumentSummaryJob(uid).set_caller("attachments_summaries")
    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        files = [models.Attachment.from_dict(doc.to_dict()) for doc in docs]
        queries = [
            gemini.DocumentSummaryQuery(doc.reference.path, file.full_text)
            for doc, file in zip(docs, files)
            if file.full_text
        ]
        _attach_legislator_context_to_summary_queries(db, queries)
        _attach_director_context_to_summary_queries(db, queries)
        increment_attempts(db, [q.doc_path for q in queries], "ai_summary_attempts")
        job.write_queries(queries)
        query_size += len(queries)
        if query_size >= _MAX_BATCH_SUMMARY_QUERY_SIZE:
            break
    if query_size <= 0:
        logger.warn("No queries to submit")
        return
    job.submit()


@scheduler_fn.on_schedule(
    schedule="*/30 00-02,21-23 * * *",
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


def _update_speeches_summaries(query_limit: int = 200):
    db = firestore.client()

    if running_jobs(db, "speeches_summaries"):
        logger.warn("Still have running jobs, skip update speeches summaries.")
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
            .where(filter=FieldFilter("ai_summary_attempts", "<", _MAX_ATTEMPTS))
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(query_limit).stream())

    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchDocumentSummaryJob(uid).set_caller("speeches_summaries")
    query_size = 0
    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        logger.debug(f"Processing {len(docs)} documents")
        last_doc = docs[-1]
        videos = [models.Video.from_dict(doc.to_dict()) for doc in docs]
        queries = [
            gemini.TranscriptSummaryQuery(
                doc.reference.path, video.transcript, video.member or ""
            )
            for doc, video in zip(docs, videos)
            if video.transcript
        ]
        _attach_legislator_context_to_summary_queries(db, queries)
        _attach_director_context_to_summary_queries(db, queries)
        increment_attempts(db, [q.doc_path for q in queries], "ai_summary_attempts")
        job.write_queries(queries)
        query_size += len(queries)
        if query_size >= _MAX_BATCH_SUMMARY_QUERY_SIZE:
            break
    job.submit()


@scheduler_fn.on_schedule(
    schedule="*/30 00-02,21-23 * * *",
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

    if running_jobs(db, "update_speech_transcripts"):
        logger.warn("Still have running jobs, skip update videos transcripts.")
        return

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        collections = (
            db.collection_group(models.SPEECH_COLLECT)
            .where(
                filter=FieldFilter(
                    "transcript_updated_at",
                    "<=",
                    dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc),
                )
            )
            .where(filter=FieldFilter("transcript_attempts", "<", 1))
        )
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(50).stream())

    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchAudioTranscriptJob(uid).set_caller(
        "update_speech_transcripts"
    )
    today = dt.datetime.now(tz=_TZ)
    transcript_task = tasks.CloudRunQueue.open("transcriptLongVideo")
    bucket = storage.bucket()
    query_size = 0
    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        videos = [models.Video.from_dict(doc.to_dict()) for doc in docs]
        queries: list[gemini.AudioTranscriptQuery] = []
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
                if today - video.start_time < dt.timedelta(days=14):
                    transcript_task.run(doc_path=doc.reference.path)
                continue
            queries.append(
                gemini.AudioTranscriptQuery(
                    doc.reference.path, base64.b64encode(blob.download_as_bytes())
                )
            )
        increment_attempts(db, [q.doc_path for q in queries], "transcript_attempts")
        job.write_queries(queries)
        query_size += len(queries)
        if query_size >= _MAX_BATCH_TRANSCRIPT_QUERY_SIZE:
            break
        while queries:
            del queries[0]
    job.submit()


@scheduler_fn.on_schedule(
    schedule="0 23 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=1800,
)
def update_legislator_speeches_summary(_):
    try:
        _update_legislator_speeches_summary()
    except Exception as e:
        logger.error(f"Fail to update legislator speech summary, {e}")
        raise RuntimeError("Fail to update legislator speech summary.") from e


def _update_legislator_speeches_summary():
    # TODO: update search engine index when we update the legislator's info
    today = dt.datetime.now(tz=_TZ)
    db = firestore.client()
    queries = []
    for row in db.collection(models.MEMBER_COLLECT).stream():
        m = models.Legislator.from_dict(row.to_dict())
        if today - m.ai_summarized_at < dt.timedelta(days=7):
            logger.warn(f"{m.name} just updated, skip it")
            continue
        speeches = _get_legislator_speeches(db, m.name)
        if not speeches:
            logger.warn(f"{m.name} has no speeches")
            continue
        queries.append(gemini.SpeechesSummaryQuery(speeches, row.reference.path))

    uid = uuid.uuid4().hex
    job = gemini.GeminiBatchSpeechesSummaryJob(uid).set_caller(
        "update_legislator_speeches_summary"
    )
    job.write_queries(queries)
    job.submit()


def _get_legislator_speeches(db: Client, name: str) -> list[gemini.MeetSpeech]:
    docs = (
        db.collection_group(models.SPEECH_COLLECT)
        .where(filter=FieldFilter("member", "==", name))
        .order_by("start_time", "DESCENDING")
        .limit(100)
        .stream()
    )
    speeches = []
    for doc in docs:
        p: str = doc.reference.path
        if not p.startswith(models.MEETING_COLLECT):
            continue
        meet_path = "/".join(p.split("/")[0:2])
        meet_doc = db.document(meet_path).get()
        if not meet_doc.exists:
            continue
        meet: models.Meeting = models.Meeting.from_dict(meet_doc.to_dict())
        video = models.Video.from_dict(doc.to_dict())
        speeches.append(gemini.MeetSpeech(meet, video))
    return speeches


@scheduler_fn.on_schedule(
    schedule="*/30 * * * *",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_2,
    timeout_sec=1800,
)
def update_document_hash_tags(_):
    try:
        for collection in [
            models.SPEECH_COLLECT,
            models.FILE_COLLECT,
            models.ATTACH_COLLECT,
            models.VIDEO_COLLECT,
        ]:
            _update_document_hash_tags(collection)
    except Exception as e:
        logger.error(f"Fail to update document hash tags, {e}")
        raise RuntimeError("Fail to update document hash tags") from e


def _update_document_hash_tags(
    collection: str,
    max_batch_queries: int = _MAX_BATCH_SUMMARY_QUERY_SIZE,
    query_limit=100,
):
    db = firestore.client()
    caller = f"update_document_hash_tags:{collection}"

    if running_jobs(db, caller):
        logger.warn(f"Still have running jobs, skip {caller}")
        return

    def get_docs_for_update(
        last_doc: DocumentSnapshot | None = None,
    ) -> list[DocumentSnapshot]:
        query: Query
        if collection in [models.MEETING_COLLECT, models.PROCEEDING_COLLECT]:
            query = db.collection(collection)
        else:
            query = db.collection_group(collection)
        collections = query.where(
            filter=FieldFilter("has_hash_tags", "==", False)
        ).where(filter=FieldFilter("has_tags_summary_attempts", "<", _MAX_ATTEMPTS))
        if last_doc is not None:
            collections = collections.start_after(last_doc)
        return list(collections.limit(query_limit).stream())

    uid = uuid.uuid4().hex
    job = gemini.GeminiHashTagsSummaryJob(uid, caller=caller)
    query_size = 0
    last_doc: DocumentSnapshot | None = None
    while docs := get_docs_for_update(last_doc):
        last_doc = docs[-1]
        queries = _build_hashtag_queries(docs, collection=collection)
        query_size += len(queries)
        job.write_queries(queries)  # type: ignore
        increment_attempts(
            db, [doc.reference.path for doc in docs], "has_tags_summary_attempts"
        )
        if query_size >= max_batch_queries:
            break
    try:
        job.submit()
    except RuntimeError as e:
        logger.error(f"Fail to submit {collection} job: {e}")


def _build_hashtag_queries(
    snapshots: list[DocumentSnapshot], collection: str
) -> list[gemini.HashTagsSummaryQuery]:
    if collection in [models.ATTACH_COLLECT, models.FILE_COLLECT]:
        attachments = [models.Attachment.from_dict(s.to_dict()) for s in snapshots]
        return [
            gemini.HashTagsSummaryQuery(
                doc_path=s.reference.path, content=doc.full_text
            )
            for s, doc in zip(snapshots, attachments)
            if doc.full_text
        ]
    elif collection in [models.VIDEO_COLLECT, models.SPEECH_COLLECT]:
        videos = [models.Video.from_dict(s.to_dict()) for s in snapshots]
        return [
            gemini.HashTagsSummaryQuery(
                doc_path=s.reference.path, content=doc.transcript
            )
            for s, doc in zip(snapshots, videos)
            if doc.transcript
        ]
    else:
        raise TypeError("Unsupported collection: " + collection)


def _attach_legislator_context_to_summary_queries(
    db: Client,
    queries: list[gemini.DocumentSummaryQuery] | list[gemini.TranscriptSummaryQuery],
):
    create_date = _get_create_date(db, queries[0].doc_path)
    term = utils.get_legislative_yuan_term(create_date)
    if not term:
        logger.error(
            "Can't determine the term for the document: " + queries[0].doc_path
        )
        raise ValueError("Can't determine the term for the document.")
    for q in queries:
        ctx = io.StringIO()
        context.attach_legislators_background(ctx, [term])
        q.context += ctx.getvalue()


def _attach_director_context_to_summary_queries(
    db: Client,
    queries: list[gemini.DocumentSummaryQuery] | list[gemini.TranscriptSummaryQuery],
):
    for q in queries:
        ctx = io.StringIO()
        ref = db.document(q.doc_path)
        vectors = [e.to_vector() for e in models.get_embeddings(ref)]
        context.attach_directors_background(ctx, vectors)
        q.context += ctx.getvalue()


def _get_create_date(db: Client, ref_path: str) -> dt.datetime:
    """Get the document's created date."""
    if ref_path.startswith(models.PROCEEDING_COLLECT):
        doc_ref = db.document("/".join(ref_path.split("/")[0:2]))
        doc = doc_ref.get()
        if not doc.exists:
            return dt.datetime.min
        return models.Proceeding.from_dict(doc.to_dict()).created_date
    elif ref_path.startswith(models.MEETING_COLLECT):
        doc_ref = db.document("/".join(ref_path.split("/")[0:2]))
        doc = doc_ref.get()
        if not doc.exists:
            return dt.datetime.min
        meet: models.Meeting = models.Meeting.from_dict(doc.to_dict())
        return meet.meeting_date_start
    else:
        return dt.datetime.now(tz=_TZ)


@scheduler_fn.on_schedule(
    schedule="0 23 * * *",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_1,
    timeout_sec=1800,
)
def update_historical_meetings(_):
    app: firebase_admin.App = firebase_admin.get_app()
    region = SupportedRegion.ASIA_EAST1
    proj = app.project_id
    token = app.credential.get_access_token().access_token
    url = f"https://{region}-{proj}.cloudfunctions.net/update_meetings_by_date"
    today = dt.datetime.now(tz=_TZ)
    for i in range(15):
        date = today - dt.timedelta(days=i)
        tw_year = date.year - 1911
        res = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"date": f"{tw_year}/" + date.strftime("%m/%d")},
            timeout=120,
        )
        res.raise_for_status()


@scheduler_fn.on_schedule(
    schedule="*/30 * * * *",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.MB_512,
    timeout_sec=1800,
)
def update_batch_job_status(_):
    db = firestore.client()

    documents = (
        db.collection(gemini.GEMINI_COLLECTION)
        .where(filter=FieldFilter("finished", "==", False))
        .where(filter=FieldFilter("status", "==", gemini.BATCH_JOB_STATUS_RUNNING))
        .stream()
    )

    for doc in documents:
        job = gemini.BatchPredictionJob(**doc.to_dict())
        status = job.poll_job_state()
        if status == gemini.JOB_STATE_QUEUED:
            continue
        elif status == gemini.JOB_STATE_CANCELLED | status == gemini.JOB_STATE_FAILED:
            job.status = gemini.BATCH_JOB_STATUS_FAILED
            job.finished = True
            doc.reference.update(dataclasses.asdict(job))
