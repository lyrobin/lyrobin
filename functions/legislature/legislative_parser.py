"""Legislature parser."""

# pylint: disable=invalid-name
import dataclasses
import datetime as dt
import json
import logging
import os

from firebase_admin import firestore, storage
from firebase_functions import firestore_fn, https_fn, logger, tasks_fn
from firebase_functions.options import (
    MemoryOption,
    RateLimits,
    RetryConfig,
    SupportedRegion,
)
from google.cloud.firestore_v1 import document
import google.cloud.firestore
from legislature import LEGISLATURE_MEETING_INFO_API, models, readers
from params import (
    DEFAULT_TIMEOUT_SEC,
    TYPESENSE_API_KEY,
)
from utils import session, tasks
from search import client as search_client


_DEFAULT_TIMEOUT = DEFAULT_TIMEOUT_SEC.value
_REQUEST_HEADEER = {
    "User-Agent": " ".join(
        [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "AppleWebKit/537.36 (KHTML, like Gecko)",
            "Chrome/91.0.4472.124",
            "Safari/537.36",
        ]
    ),
}
_REGION = SupportedRegion.ASIA_EAST1


@https_fn.on_request(region=_REGION)
def update_meetings(request: https_fn.Request) -> https_fn.Response:
    """
    Update the meetings in the database.

    Args:
        term (str): The term to update the meetings for.
    """
    logger.log("Updating meetings")
    term = request.args.get("term", type=int)
    period = request.args.get("period", "", type=str)
    limit = request.args.get("limit", 0, type=int)
    logger.debug(f"Term: {term}, Period: {period}")
    res = session.new_legacy_session().get(
        LEGISLATURE_MEETING_INFO_API.value,
        headers=_REQUEST_HEADEER,
        params={"term": term, "fileType": "json", "sessionPeriod": period},
        timeout=_DEFAULT_TIMEOUT,
    )
    if res.status_code != 200:
        logger.error(f"Error getting meetSings: {res.status_code}")
        return https_fn.Response(
            json.dumps(
                {
                    "error": "Error getting meetings.",
                    "term": term,
                }
            ),
            status=res.status_code,
            content_type="application/json",
        )
    db = firestore.client()
    data: dict = json.loads(res.text)
    batch = db.batch()
    collection = db.collection(models.MEETING_COLLECT)
    count = 0
    data_list = data.get("dataList", [])
    if limit > 0 and len(data_list) > limit:
        data_list = data_list[0:limit]
    for m in data_list:
        try:
            meet: models.Meeting = models.Meeting.from_dict(m)
            if not meet.document_id:
                continue
            doc_ref = collection.document(meet.document_id)
            doc = doc_ref.get()
            if doc.exists and doc != meet:
                batch.update(doc_ref, meet.asdict())
                continue
            batch.set(doc_ref, meet.asdict())
            count += 1
        except (TypeError, ValueError) as e:
            logger.error(f"Error parsing meeting: {m}, error: {e}")
    batch.commit()
    return https_fn.Response(
        json.dumps({"count": count, "term": term}),
        status=200,
        content_type="application/json",
    )


@firestore_fn.on_document_created(
    document="meetings/{meetNo}", region=_REGION, secrets=[TYPESENSE_API_KEY]
)
def on_meeting_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot],
):
    """Fetch the meeting from the web."""
    try:
        return _fetch_meeting_when_created(event)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Error fetching meeting: {event.params}") from e


def _fetch_meeting_when_created(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot],
):
    """Fetch the meeting from the web."""
    db = firestore.client()
    se = search_client.DocumentSearchEngine.create(api_key=TYPESENSE_API_KEY.value)
    meet_no = event.params["meetNo"]
    meet_ref = db.collection(models.MEETING_COLLECT).document(meet_no)
    meet_doc = meet_ref.get()
    if not meet_doc.exists:
        raise RuntimeError(f"Meeting {meet_no} does not exist.")
    meet: models.Meeting = models.Meeting.from_dict(meet_doc.to_dict())
    se.index(meet_ref.path, search_client.DocType.MEETING)
    q = tasks.CloudRunQueue.open("fetchMeetingFromWeb")
    q.run(meet_no=meet_no, url=meet.get_url())


@firestore_fn.on_document_updated(
    document="meetings/{meetNo}", region=_REGION, secrets=[TYPESENSE_API_KEY]
)
def on_meeting_update(
    event: firestore_fn.Event[firestore_fn.Change[firestore_fn.DocumentSnapshot]],
):
    """Update the meeting."""
    try:
        se = search_client.DocumentSearchEngine.create(api_key=TYPESENSE_API_KEY.value)
        meet_no = event.params["meetNo"]
        se.index(f"{models.MEETING_COLLECT}/{meet_no}", search_client.DocType.MEETING)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Failed when updating meeting. {event.params}") from e


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=300),
    rate_limits=RateLimits(max_concurrent_dispatches=20),
    region=_REGION,
    timeout_sec=300,
)
def fetchMeetingFromWeb(request: tasks_fn.CallableRequest) -> any:
    """Fetch the meeting from the web."""
    try:
        _fetch_meeting_from_web(request)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Error fetching meeting: {request.data}") from e


def _fetch_meeting_from_web(request: tasks_fn.CallableRequest) -> any:
    logger.debug(f"Fetch meeting from web: {request.data}")
    meet_no = request.data["meetNo"]
    url = request.data["url"]
    db = firestore.client()
    meet_doc_ref = db.collection(models.MEETING_COLLECT).document(meet_no)
    meet_doc = meet_doc_ref.get()
    meet: models.Meeting = None
    if meet_doc.exists:
        meet = models.Meeting.from_dict(meet_doc.to_dict())
    else:
        meet = models.Meeting.from_dict({"meetingNo": meet_no})
        meet_doc_ref.set(meet.asdict(), merge=True)

    if dt.datetime.now(dt.timezone.utc) - meet.last_update_time < dt.timedelta(days=1):
        return
    r = readers.LegislativeMeetingReader.open(url=url)
    if r.get_meeting_name() and not meet.meeting_name:
        meet.meeting_name = r.get_meeting_name()

    if r.get_meeting_content() and not meet.meeting_content:
        meet.meeting_content = r.get_meeting_content()

    if r.get_meeting_room() and not meet.meeting_room:
        meet.meeting_room = r.get_meeting_room()

    if r.get_meeting_date_desc() and not meet.meeting_date_desc:
        meet.meeting_date_desc = r.get_meeting_date_desc()

    ivods = []
    for v in r.get_videos():
        try:
            m = models.IVOD(name=v.name, url=v.url)
            ivods.append(m)
        except ValueError as e:
            logger.error(f"Error parsing IVOD: {v}, error: {e}")

    meeting_files = [
        models.MeetingFile(name=a.name, url=a.url)
        for a in r.get_files(allow_download=True)
    ]
    proceedings = [
        models.Proceeding(name=p.name, url=p.url, bill_no=p.bill_no)
        for p in r.get_related_proceedings()
    ]

    meet.last_update_time = dt.datetime.now(dt.timezone.utc)
    meet_doc_ref.update(meet.asdict())

    batch = db.batch()

    ivods_collect = meet_doc_ref.collection(models.IVOD_COLLECT)
    for v in ivods:
        batch.set(ivods_collect.document(v.document_id), v.asdict(), merge=True)

    files_collect = meet_doc_ref.collection(models.FILE_COLLECT)
    for f in meeting_files:
        batch.set(files_collect.document(f.document_id), f.asdict(), merge=True)

    root_proceedings_collect = db.collection(models.PROCEEDING_COLLECT)
    proceedings_collect = meet_doc_ref.collection(models.PROCEEDING_COLLECT)
    for p in proceedings:
        batch.set(proceedings_collect.document(p.document_id), p.asdict(), merge=True)
        batch.set(
            root_proceedings_collect.document(p.document_id), p.asdict(), merge=True
        )

    batch.commit()


@firestore_fn.on_document_created(
    document="meetings/{meetNo}/proceedings/{billNo}", region=_REGION
)
def on_meeting_proceedings_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot],
):
    """Handle meeting proceedings creation"""
    try:

        meet_no = event.params["meetNo"]
        bill_no = event.params["billNo"]
        _on_meeting_proceedings_create(meet_no, bill_no)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(
            f"Error handling meeting proceedings creation: {event.params}"
        ) from e


def _on_meeting_proceedings_create(meet_no: str, bill_no: str):
    db = firestore.client()
    ref = db.document(
        f"{models.MEETING_COLLECT}/{meet_no}/{models.PROCEEDING_COLLECT}/{bill_no}"
    )
    doc = ref.get()
    if not doc.exists:
        return
    proc: models.Proceeding = models.Proceeding.from_dict(doc.to_dict())
    q = tasks.CloudRunQueue.open("fetchProceedingFromWeb")
    q.run(bill_no=proc.bill_no, url=proc.url)


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=300),
    rate_limits=RateLimits(max_concurrent_dispatches=20),
    region=_REGION,
    timeout_sec=300,
)
def fetchProceedingFromWeb(request: tasks_fn.CallableRequest) -> any:
    try:
        _fetch_proceeding_from_web(request)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Error fetching proceeding: {request.data}") from e


def _find_proceeding_created_date(
    db: google.cloud.firestore.Client, m: models.Proceeding
) -> dt.datetime:
    proceedings = (
        db.collection_group(models.PROCEEDING_COLLECT)
        .where("bill_no", "==", m.bill_no)
        .limit(100)
        .stream()
    )
    created_date: dt.datetime = dt.datetime.max
    for proc in proceedings:
        proc_ref: document.DocumentReference = proc.reference
        if not proc_ref.path.startswith(models.MEETING_COLLECT):
            continue
        meet_ref = db.document("/".join(proc_ref.path.split("/")[0:2]))
        meet_doc = meet_ref.get()
        if not meet_doc.exists:
            continue
        meet: models.Meeting = models.Meeting.from_dict(meet_doc.to_dict())
        if meet.meeting_date_start < created_date:
            created_date = meet.meeting_date_start
    return created_date


def _fetch_proceeding_from_web(request: tasks_fn.CallableRequest) -> any:
    bill_no: int = request.data["billNo"]
    url: str = request.data["url"]
    db = firestore.client()

    proc_ref = db.collection(models.PROCEEDING_COLLECT).document(bill_no)
    proc_doc = proc_ref.get()

    proc: models.Proceeding
    if proc_doc.exists:
        proc = models.Proceeding.from_dict(proc_doc.to_dict())
    else:
        proc = models.Proceeding.from_dict({"billNo": bill_no, "url": url})
        proc_ref.set(proc.asdict(), merge=True)

    if dt.datetime.now(dt.timezone.utc) - proc.last_update_time < dt.timedelta(days=1):
        return

    r = readers.ProceedingReader.open(url=url)
    related_bills = r.get_related_bills()
    proposers = r.get_proposers()
    sponsors = r.get_sponsors()
    status = r.get_status()
    progress = [dataclasses.asdict(s) for s in r.get_progress()]
    attachments = [
        models.Attachment(name=a.name, url=a.url) for a in r.get_attachments()
    ]

    if related_bills:
        proc.related_bills = related_bills

    if proposers and not proc.proposers:
        # The proposers are unlikely to change
        proc.proposers = proposers

    if sponsors and not proc.sponsors:
        # The sponsors are unlikely to change
        proc.sponsors = sponsors

    if status:
        proc.status = status

    if progress:
        proc.progress = progress

    proc.created_date = _find_proceeding_created_date(db, proc)
    proc.last_update_time = dt.datetime.now()
    proc_ref.update(proc.asdict())

    attach_collect = proc_ref.collection(models.ATTACH_COLLECT)
    for a in attachments:
        attach_collect.document(a.document_id).set(a.asdict(), merge=True)


@firestore_fn.on_document_created(
    document="proceedings/{procNo}/attachments/{attachNo}",
    region=_REGION,
    memory=MemoryOption.GB_2,
)
def on_proceedings_attachment_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot],
):
    """Handler on proceedings attachment create."""
    try:
        proc_no = event.params["procNo"]
        attach_no = event.params["attachNo"]
        db = firestore.client()

        attach_ref = db.document(
            f"{models.PROCEEDING_COLLECT}/{proc_no}/{models.ATTACH_COLLECT}/{attach_no}"
        )
        _upsert_attachment_content(attach_ref)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(
            f"Error on_proceedings_attachment_create: {event.params}"
        ) from e


def _upsert_attachment_content(ref: document.DocumentReference):
    """Upsert attachment content."""
    doc = ref.get()
    if not doc.exists:
        return
    attach: models.Attachment = models.Attachment.from_dict(doc.to_dict())
    r = readers.DocumentReader.open(attach.url)
    if r is None:
        return

    attach.full_text = r.content
    ref.update(attach.asdict())


@firestore_fn.on_document_created(
    document="meetings/{meetNo}/files/{fileNo}",
    region=_REGION,
    memory=MemoryOption.GB_2,
)
def on_meetings_attached_file_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot],
):
    """Handler on meetings attached file create."""
    try:
        meet_no = event.params["meetNo"]
        file_no = event.params["fileNo"]
        db = firestore.client()

        file_ref = db.document(
            f"{models.MEETING_COLLECT}/{meet_no}/{models.FILE_COLLECT}/{file_no}"
        )
        _upsert_attachment_content(file_ref)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(
            f"Error on_proceedings_attachment_create: {event.params}"
        ) from e


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=300),
    rate_limits=RateLimits(max_concurrent_dispatches=20),
    region=_REGION,
    timeout_sec=300,
)
def fetchIVODFromWeb(request: tasks_fn.CallableRequest) -> any:
    """Handler on fetch ivod from web."""
    try:
        meet_no = request.data["meetNo"]
        ivod_no = request.data["ivodNo"]
        _fetch_ivod_from_web(meet_no, ivod_no)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Error fetching ivod: {request.data}") from e


def _fetch_ivod_from_web(meet_no: str, ivod_no: str):
    db = firestore.client()
    ref = db.document(
        f"{models.MEETING_COLLECT}/{meet_no}/{models.IVOD_COLLECT}/{ivod_no}"
    )
    doc = ref.get()
    if not doc.exists:
        return
    ivod: models.IVOD = models.IVOD.from_dict(doc.to_dict())
    r = readers.IvodReader.open(ivod.url)

    videos = [models.Video(url=v.url) for v in r.get_videos()]
    speeches = [
        models.Video(url=v.url, member=v.member) for v in r.get_member_speeches()
    ]

    batch = db.batch()

    for v in videos:
        batch.set(
            ref.collection(models.VIDEO_COLLECT).document(v.document_id),
            v.asdict(),
            merge=True,
        )

    for v in speeches:
        batch.set(
            ref.collection(models.SPEECH_COLLECT).document(v.document_id),
            v.asdict(),
            merge=True,
        )
    batch.commit()


@firestore_fn.on_document_created(
    document="meetings/{meetNo}/ivods/{ivodNo}", region=_REGION
)
def on_meeting_ivod_create(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]):
    """Handler on meeting ivod create."""
    try:
        meet_no = event.params["meetNo"]
        ivod_no = event.params["ivodNo"]
        q = tasks.CloudRunQueue.open("fetchIVODFromWeb")
        q.run(meet_no=meet_no, ivod_no=ivod_no)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Error on_meeting_ivod_create: {event.params}") from e


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=600),
    rate_limits=RateLimits(max_concurrent_dispatches=20),
    cpu=4,
    memory=MemoryOption.GB_4,
    region=_REGION,
    timeout_sec=1800,
    max_instances=30,
    concurrency=2,
)
def downloadVideo(request: tasks_fn.CallableRequest) -> any:
    """Handler on download video."""
    try:
        meet_no = request.data["meetNo"]
        ivod_no = request.data["ivodNo"]
        video_no = request.data["videoNo"]
        _download_video(meet_no, ivod_no, video_no)
    except Exception as e:
        logger.error(f"fail to download video: {e}")
        raise RuntimeError(f"Error downloading video: {request.data}") from e


def _download_video(meet_no: str, ivod_no: str, video_no: str):
    db = firestore.client()

    ivod_ref = db.document(
        f"{models.MEETING_COLLECT}/{meet_no}/{models.IVOD_COLLECT}/{ivod_no}"
    )
    ivod_doc = ivod_ref.get()
    if not ivod_doc.exists:
        return
    video_ref, collect = _find_video_in_ivod(ivod_ref, video_no)
    if not video_ref:
        return

    speech_count = video_ref.collection(models.SPEECH_COLLECT).count().get()[0][0].value
    if collect == models.VIDEO_COLLECT and speech_count > 0:
        return

    video: models.Video = models.Video.from_dict(video_ref.get().to_dict())
    logger.debug(f"Open video: {video.url}")
    r = readers.VideoReader.open(video.url)

    if r.meta.duration > dt.timedelta(hours=3):
        logger.warn("Video %s is too long. (> 3 hours)", video.url)
        return
    elif r.meta.duration <= dt.timedelta.min:
        logger.warn("Video %s doesn't have duration info, skip it.", video.url)
        return
    logger.debug(f"Prepare to download video: {video.url}")
    video.playlist = r.playlist_url
    video.start_time = r.meta.start_time

    clips = []
    temp_mp4 = []
    bucket = storage.bucket()

    def _upload_clip(i: int) -> str:
        blob = bucket.blob(f"videos/{video.document_id}/clips/{i}.mp4")
        gs_path = f"gs://{bucket.name}/{blob.name}"
        if blob.exists():
            logger.warn(
                f"blob exists: {gs_path}, remove blobs if you've changed the clip size."
            )
            return gs_path
        mp4 = r.download_mp4(i)
        logger.debug("download mp4: %s", mp4)
        with open(mp4, "rb") as f:
            blob.upload_from_file(f, content_type="video/mp4")
        try:
            os.remove(mp4)
        except (OSError, FileNotFoundError, IOError) as e:
            temp_mp4.append(mp4)
            logger.error(e)
        return gs_path

    for i in range(min(r.clips_count, 10)):
        # Safe guarded, prevent downloading too many chunks.
        clips.append(_upload_clip(i))
    if clips:
        video.clips = clips
    video_ref.update(video.asdict())
    for mp4 in temp_mp4:
        os.remove(mp4)


def _find_video_in_ivod(
    ivod_ref: document.DocumentReference, video_no: str
) -> tuple[document.DocumentReference | None, str]:
    video_ref: document.DocumentReference = ivod_ref.collection(
        models.VIDEO_COLLECT
    ).document(video_no)
    if video_ref.get().exists:
        return video_ref, models.VIDEO_COLLECT

    video_ref = ivod_ref.collection(models.SPEECH_COLLECT).document(video_no)
    if video_ref.get().exists:
        return video_ref, models.SPEECH_COLLECT

    return None, ""


@firestore_fn.on_document_created(
    document="meetings/{meetNo}/ivods/{ivodNo}/{videoCollect}/{videoNo}", region=_REGION
)
def on_ivod_video_create(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]):
    """Handler on ivod video create."""
    try:
        meet_no = event.params["meetNo"]
        ivod_no = event.params["ivodNo"]
        video_no = event.params["videoNo"]
        q = tasks.CloudRunQueue.open("downloadVideo")
        q.run(meet_no=meet_no, ivod_no=ivod_no, video_no=video_no)
    except Exception as e:
        logger.error(f"Fail to on_ivod_video_create: {event.params}")
        raise RuntimeError(f"Fail to on_ivod_video_create: {event.params}") from e
