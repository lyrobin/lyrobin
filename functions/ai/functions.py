"""Firebase cloud functions."""

from ai import gemini
from firebase_admin import firestore  # type: ignore
from firebase_functions import firestore_fn, tasks_fn
from firebase_functions.options import (
    MemoryOption,
    RateLimits,
    RetryConfig,
    SupportedRegion,
)
from google.cloud.firestore import Client, FieldFilter  # type: ignore
from utils import tasks

_MAX_CONCURRENT_BATCH_JOBS = 1

_REGION = SupportedRegion.ASIA_EAST1


def running_jobs(db: Client, quota: str = gemini.QUOTA_BATCH_PREDICTION) -> int:
    return int(
        db.collection(gemini.GEMINI_COLLECTION)
        .where(filter=FieldFilter("quota", "==", quota))
        .where(filter=FieldFilter("status", "==", gemini.BATCH_JOB_STATUS_RUNNING))
        .where(filter=FieldFilter("finished", "==", False))
        .count()
        .get()[0][0]
        .value
    )


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=2, max_backoff_seconds=300),
    rate_limits=RateLimits(max_concurrent_dispatches=1),
    memory=MemoryOption.MB_512,
    max_instances=1,
    concurrency=1,
    region=gemini.GEMINI_REGION,
)
def runGeminiBatchPredictionJob(_: tasks_fn.CallableRequest):
    db = firestore.client()
    if running_jobs(db) >= _MAX_CONCURRENT_BATCH_JOBS:
        return
    pending_tasks = (
        db.collection(gemini.GEMINI_COLLECTION)
        .where(filter=FieldFilter("finished", "==", False))
        .where(filter=FieldFilter("status", "==", gemini.BATCH_JOB_STATUS_NEW))
        .where(filter=FieldFilter("quota", "==", gemini.QUOTA_BATCH_PREDICTION))
        .order_by("submit_time", "ASCENDING")
        .limit(_MAX_CONCURRENT_BATCH_JOBS)
        .stream()
    )

    for task in pending_tasks:
        m = gemini.BatchPredictionJob(**task.to_dict())
        job = m.to_gemini_job()
        job.run()


@firestore_fn.on_document_created(
    document="gemini/{jobId}", region=_REGION, memory=MemoryOption.MB_512
)
def on_gemini_job_create(_: firestore_fn.Event[firestore_fn.DocumentSnapshot | None]):
    q = tasks.CloudRunQueue.open(
        "runGeminiBatchPredictionJob", region=gemini.GEMINI_REGION
    )
    q.run()


@firestore_fn.on_document_updated(
    document="gemini/{jobId}", region=_REGION, memory=MemoryOption.MB_512
)
def on_gemini_job_update(
    _: firestore_fn.Event[firestore_fn.Change[firestore_fn.DocumentSnapshot | None]],
):
    q = tasks.CloudRunQueue.open(
        "runGeminiBatchPredictionJob", region=gemini.GEMINI_REGION
    )
    q.run()
