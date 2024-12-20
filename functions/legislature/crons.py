"""Module for crons jobs."""

import base64
import collections
import dataclasses
import datetime as dt
import io
import urllib.parse
import uuid

import firebase_admin  # type: ignore
import requests
import utils
from ai import context, gemini
from ai.batch import weekly_news
from firebase_admin import firestore, storage  # type: ignore
from firebase_functions import logger, scheduler_fn
from firebase_functions.options import MemoryOption, SupportedRegion, Timezone
from google.cloud.firestore import DocumentSnapshot  # type: ignore
from google.cloud.firestore import Client, FieldFilter, Increment, Query
from legislature import models, reports
from utils import tasks, timeutil, cloudbatch

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
    schedule="*/30 13-15,21-23 * * *",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=1800,
)
def update_speeches_summaries(_):
    pass  # TODO: remove this function after new approach is ready.
    # try:
    #     _update_speeches_summaries()
    # except Exception as e:
    #     logger.error(f"Fail to update speeches summaries, {e}")
    #     raise RuntimeError("Fail to update speeches summaries.") from e


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
    schedule="*/30 13-15,21-23 * * *",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
    timeout_sec=1800,
)
def update_speech_transcripts(_):
    pass  # TODO: remove this function after new approach is ready.
    # try:
    #     _update_speech_transcripts()
    # except Exception as e:
    #     logger.error(f"Fail to update videos transcripts, {e}")
    #     raise RuntimeError("Fail to update videos transcripts.") from e


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
            .where(filter=FieldFilter("transcript_attempts", "<", _MAX_ATTEMPTS))
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
            logger.debug(f"Processing {doc.reference.path}")
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
    cpu=1,
    memory=MemoryOption.GB_1,
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
    db = firestore.client()
    q = tasks.CloudRunQueue.open(
        "updateLegislatorSpeechesSummary", region=gemini.GEMINI_REGION
    )
    today = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    term = timeutil.get_legislative_yuan_term(today)
    docs = (
        db.collection(models.MEMBER_COLLECT)
        .where(filter=FieldFilter("terms", "array_contains", str(term)))
        .stream()
    )
    for doc in docs:
        m = models.Legislator.from_dict(doc.to_dict())
        q.run(name=m.name)


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
            # models.SPEECH_COLLECT, # TODO: remove this line after new approach is ready.
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
        if collection in [models.SPEECH_COLLECT, models.VIDEO_COLLECT]:
            collections = collections.where(
                filter=FieldFilter("has_transcript", "==", True)
            )
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
    current_term = utils.get_legislative_yuan_term(dt.datetime.now(tz=_TZ))
    if not current_term:
        raise ValueError("Can't determine the current term.")
    context_cache: dict[int, str] = {}
    for q in queries:
        term = (
            utils.get_legislative_yuan_term(_get_create_date(db, q.doc_path))
            or current_term
        )
        if term not in context_cache:
            buffer = io.StringIO()
            context.attach_legislators_background(buffer, [term])
            context_cache[term] = buffer.getvalue()
        q.context += context_cache[term]


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
        return models.Proceeding.from_dict(doc.to_dict()).derive_created_date()
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
    schedule="0 13-15,21-23 * * *",
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


@scheduler_fn.on_schedule(
    schedule="0 17 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_1,
    timeout_sec=1800,
    retry_count=2,
)
def generate_weekly_report(_):
    try:
        today = dt.datetime.now(tz=_TZ)
        monday = today - dt.timedelta(days=today.weekday())
        saturday = monday + dt.timedelta(days=5)
        _generate_weekly_report(monday, saturday)
    except Exception as e:
        logger.error(f"Fail to generate weekly report, {e}")
        raise RuntimeError("Fail to generate weekly report.") from e


def _get_meetings_in_range(
    start: dt.datetime, end: dt.datetime, db: Client = None
) -> list[models.MeetingModel]:
    if db is None:
        db = firestore.client()
    docs = (
        db.collection(models.MEETING_COLLECT)
        .where("meeting_date_start", ">=", start)
        .where("meeting_date_start", "<=", end)
        .stream()
    )
    meetings = [models.MeetingModel.from_ref(doc.reference) for doc in docs]
    docs = (
        db.collection_group(models.SPEECH_COLLECT)
        .where("start_time", ">=", start)
        .where("start_time", "<=", end)
        .stream()
    )
    meetings.extend(models.SpeechModel(doc.reference).meeting for doc in docs)
    meetings = list(
        {m.value.document_id: m for m in meetings}.values()
    )  # remove duplicates
    return meetings


def _generate_weekly_report(start: dt.datetime, end: dt.datetime):
    db = firestore.client()

    meetings_by_unit = collections.defaultdict(list)
    for m in _get_meetings_in_range(start, end, db):
        meetings_by_unit[m.value.meeting_unit].append(m)

    all_meetings = []
    for _, v in meetings_by_unit.items():
        all_meetings.extend(sorted(v, key=lambda x: x.value.meeting_date_start))

    report_txt = reports.dumps_meetings_report(all_meetings)
    transcript_txt = reports.dump_meeting_transcripts_in_json(
        all_meetings, start=start, end=end
    )

    bucket = storage.bucket()
    week_number = start.isocalendar().week

    # all report
    blob = bucket.blob(f"reports/weekly/w{week_number}.md")
    blob.upload_from_string(report_txt, content_type="text/markdown; charset=utf-8")
    report_uri = f"gs://{bucket.name}/{blob.name}"

    # transcript
    transcript_blob = bucket.blob(f"reports/weekly/w{week_number}_transcripts.txt")
    transcript_blob.upload_from_string(
        transcript_txt, content_type="text/plain; charset=utf-8"
    )
    transcript_uri = f"gs://{bucket.name}/{transcript_blob.name}"

    weekly_news.start_generate_weekly_news(
        weekly_news.GenerateWeeklyNewsContext(
            report_uri=report_uri,
            transcript_uri=transcript_uri,
            start=start,
            end=end,
        ),
    )


@scheduler_fn.on_schedule(
    schedule="0 5 * * 2-6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_1,
    timeout_sec=1800,
    retry_count=2,
)
def generate_daily_podcast(_):
    today = dt.datetime.now(tz=_TZ)
    start = dt.datetime(
        today.year, today.month, today.day, 0, 0, tzinfo=_TZ
    ) - dt.timedelta(days=1)
    end = dt.datetime(start.year, start.month, start.day, 23, 59, tzinfo=_TZ)
    logger.debug(f"Generate podcast for {start} - {end}")
    db = firestore.client()
    docs = (
        db.collection_group(models.SPEECH_COLLECT)
        .where(filter=FieldFilter("start_time", ">=", start))
        .where(filter=FieldFilter("start_time", "<=", end))
        .stream()
    )
    speeches = [models.SpeechModel(doc.reference) for doc in docs]
    transcripts = reports.dump_speeches(speeches)
    bucket = storage.bucket()
    dated_folder = start.strftime("%Y%m%d")
    bucket.blob(f"podcast/{dated_folder}/transcripts.txt").upload_from_string(
        transcripts, content_type="text/plain; charset=utf-8"
    )
    buf = io.StringIO()
    context.attach_legislators_background(
        buf, [timeutil.get_legislative_yuan_term(start)]
    )
    bucket.blob(f"podcast/{dated_folder}/background.txt").upload_from_string(
        buf.getvalue(), content_type="text/markdown; charset=utf-8"
    )
    job = cloudbatch.create_container_job(
        "asia-east1-docker.pkg.dev/taiwan-legislative-search/cloud-run-artifacts/podcast",
        job_name="podcast-" + dated_folder + "-" + uuid.uuid4().hex,
        env_vars={"PODCAST_DATE": start.strftime("%Y-%m-%d")},
        secret_env_vars={
            "YATING_API_KEY": "projects/661598081211/secrets/YATING_API_KEY/versions/latest",
            "YOUTUBE_CREDS": "projects/661598081211/secrets/LYROBIN_YOUTUBE_CRED/versions/latest",
        },
    )
    logger.info(f"Job {job.name} created.")
