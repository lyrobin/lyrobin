"""Module for crons jobs."""

import datetime as dt
import uuid

from ai import gemini
from firebase_admin import firestore  # type: ignore
from firebase_functions import logger, scheduler_fn
from firebase_functions.options import Timezone, MemoryOption
from google.cloud.firestore import DocumentSnapshot, FieldFilter  # type: ignore
from legislature import models

_TZ = Timezone("Asia/Taipei")


@scheduler_fn.on_schedule(
    schedule="0 22 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
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
    schedule="0 22 * * 6",
    timezone=_TZ,
    region=gemini.GEMINI_REGION,
    max_instances=2,
    concurrency=2,
    memory=MemoryOption.GB_4,
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
        gemini.GeminiBatchEmbeddingJob.create(uid).submit(queries)
