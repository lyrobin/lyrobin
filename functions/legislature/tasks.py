import datetime as dt

import opencc  # type: ignore
from ai import gemini
from firebase_admin import firestore  # type: ignore
from firebase_functions import logger, tasks_fn
from firebase_functions.options import (
    MemoryOption,
    RateLimits,
    RetryConfig,
)
from legislature import models


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=2, max_backoff_seconds=300),
    rate_limits=RateLimits(max_concurrent_dispatches=50),
    max_instances=20,
    memory=MemoryOption.MB_512,
    timeout_sec=600,
    region=gemini.GEMINI_REGION,
)
def summarizeVideo(request: tasks_fn.CallableRequest):
    try:
        doc_path = request.data["path"]
        logger.info(f"summarize video: {doc_path}")
        _summarize_video(doc_path)
    except Exception as e:
        logger.error(e)
        raise RuntimeError(f"fail to summarize video: {doc_path}") from e


def _summarize_video(doc_path: str):
    db = firestore.client()
    ref = db.document(doc_path)
    doc = ref.get()
    if not doc.exists:
        raise RuntimeError(f"{doc_path} doesn't exist.")
    v = models.Video.from_dict(doc.to_dict())
    if len(v.clips) != 1:
        logger.warn(f"Multiple clips video is not supported: {doc_path}")
        return
    clip = v.clips[0]
    if v.member:
        summary = gemini.GeminiSpeechSummaryJob(v.member, clip).run()
    else:
        summary = gemini.GeminiVideoSummaryJob(clip).run()
    if not summary:
        raise RuntimeError(f"fail to summarize {doc_path}")
    cc = opencc.OpenCC("s2tw")
    v.ai_summary = cc.convert(summary)
    v.ai_summarized = True
    v.ai_summarized_at = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    ref.update(v.asdict())
