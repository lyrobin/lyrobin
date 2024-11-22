import datetime as dt
from urllib import parse
import pathlib
import tempfile

import opencc  # type: ignore
from ai import gemini
from ai import langchain
from ai.batch import legislators_recent_speeches_summary
from firebase_admin import firestore, storage  # type: ignore
from firebase_functions import logger, tasks_fn
from firebase_functions.options import (
    MemoryOption,
    RateLimits,
    RetryConfig,
    SupportedRegion,
)
from legislature import models, readers

_REGION = SupportedRegion.ASIA_EAST1


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


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=600),
    rate_limits=RateLimits(max_concurrent_dispatches=20),
    max_instances=20,
    cpu=4,
    memory=MemoryOption.GB_4,
    timeout_sec=1800,
    region=_REGION,
    concurrency=2,
)
def extractAudio(request: tasks_fn.CallableRequest):
    try:
        doc_path = request.data["path"]
        logger.info(f"extract audio: {doc_path}")
        _extractAudio(doc_path)
    except Exception as e:
        logger.error(e)
        raise RuntimeError("fail to extract audio") from e


def _extractAudio(doc_path: str):
    db = firestore.client()
    ref = db.document(doc_path)
    doc = ref.get()
    if not doc.exists:
        raise RuntimeError(f"{doc_path} doesn't exist.")
    v = models.Video.from_dict(doc.to_dict())

    bucket = storage.bucket()
    audios = []
    for clip in v.clips:
        url = parse.urlparse(clip)
        clip_path = pathlib.PurePath(url.path.strip("/"))
        audio_path = (
            clip_path.parent.parent
            / "audio"
            / clip_path.name.replace(clip_path.suffix, ".mp3")
        )
        gs_audio_path = f"gs://{bucket.name}/{audio_path.as_posix()}"

        if (blob := bucket.blob(audio_path.as_posix())).exists():
            logger.warn(f"audio {blob.name} exists, remove it to download again.")
            audios.append(gs_audio_path)
            continue

        blob = bucket.blob(url.path.strip("/"))
        with tempfile.TemporaryDirectory(delete=False) as tempdir:
            temp_folder = pathlib.Path(tempdir)
            mp4 = temp_folder / clip_path.name
            with mp4.open("wb") as f:
                blob.download_to_file(f)
            mp3 = temp_folder / clip_path.name.replace(clip_path.suffix, ".mp3")
            mp3 = readers.AudioReader(mp4).to_mp3(mp3)
            with mp3.open("rb") as f:
                bucket.blob(audio_path.as_posix()).upload_from_file(f)

        audios.append(gs_audio_path)
        v.audios = audios
    ref.update(v.asdict())


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=600),
    rate_limits=RateLimits(max_concurrent_dispatches=5),
    max_instances=5,
    cpu=1,
    memory=MemoryOption.GB_1,
    timeout_sec=1800,
    region=gemini.GEMINI_REGION,
    concurrency=1,
)
def generateNewsReport(request: tasks_fn.CallableRequest):
    db = firestore.client()
    ref = db.collection(models.NEWS_REPORT_COLLECT).document(request.data["doc"])
    if not ref.get().exists:
        raise RuntimeError(f"news report {request.data['doc']} doesn't exist.")
    news_report = models.NewsReport.from_dict(ref.get().to_dict())
    transcript_content = news_report.get_transcript_text()
    weekly_news = langchain.generate_weekly_news_with_title(
        transcript_content, news_report.title
    )
    keywords = langchain.generate_news_keywords(weekly_news)
    legislators = langchain.search_news_stakeholders(transcript_content, weekly_news)
    cc = opencc.OpenCC("s2tw")
    news_report.content = cc.convert(weekly_news.content)
    news_report.keywords = keywords
    news_report.legislators = legislators[0:10]
    news_report.is_ready = True

    ref.update(news_report.asdict())


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=600),
    rate_limits=RateLimits(max_concurrent_dispatches=5),
    max_instances=5,
    cpu=1,
    memory=MemoryOption.GB_1,
    timeout_sec=1800,
    region=gemini.GEMINI_REGION,
    concurrency=1,
)
def updateLegislatorSpeechesSummary(request: tasks_fn.CallableRequest):
    name = request.data["name"]
    logger.info(f"update legislator speeches summary: {name}")
    db = firestore.client()
    docs = db.collection(models.MEMBER_COLLECT).limit(1).get()
    if not docs:
        raise RuntimeError(f"no member found: {name}")
    today = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    m = models.LegislatorModel(docs[0].reference)
    if (s := m.latest_summary) and s.value.created_at > today - dt.timedelta(days=6):
        raise RuntimeError(f"recent speeches summary is up-to-date: {name}")
    legislators_recent_speeches_summary.start_summary_legislator_recent_speeches(name)
