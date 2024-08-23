"""Legislature parser."""

# mypy: allow-redefinition
# pylint: disable=invalid-name,no-member
import dataclasses
import datetime as dt
import json
import logging
import os
from typing import Any

import google.cloud.firestore  # type: ignore
from ai import embeddings, gemini
from firebase_admin import firestore, storage  # type: ignore
from firebase_functions import firestore_fn, https_fn, logger, tasks_fn
from firebase_functions.options import (
    MemoryOption,
    RateLimits,
    RetryConfig,
    SupportedRegion,
)
from google.cloud.firestore_v1 import document
from legislature import (
    LEGISLATURE_LEGISLATOR_INFO_API,
    LEGISLATURE_MEETING_INFO_API,
    LEGISLATURE_PPG_API,
    models,
    readers,
)
from params import DEFAULT_TIMEOUT_SEC, TYPESENSE_API_KEY
from search import client as search_client
from utils import session, tasks

_DEFAULT_TIMEOUT = DEFAULT_TIMEOUT_SEC.value
_REGION = SupportedRegion.ASIA_EAST1


@https_fn.on_request(region=_REGION, memory=MemoryOption.MB_512)
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
    page = request.args.get("page", 0, type=int)
    logger.debug(f"Term: {term}, Period: {period}")
    res = session.new_legacy_session().get(
        LEGISLATURE_MEETING_INFO_API.value,
        headers=session.REQUEST_HEADER,
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
        base = page * limit
        data_list = data_list[base : base + limit]
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
    document="meetings/{meetNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.MB_512,
)
def on_meeting_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
):
    """Fetch the meeting from the web."""
    try:
        return _fetch_meeting_when_created(event)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Error fetching meeting: {event.params}") from e


def _fetch_meeting_when_created(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
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
    document="meetings/{meetNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.MB_512,
)
def on_meeting_update(
    event: firestore_fn.Event[
        firestore_fn.Change[firestore_fn.DocumentSnapshot | None]
    ],
):
    """Update the meeting."""
    try:
        se = search_client.DocumentSearchEngine.create(api_key=TYPESENSE_API_KEY.value)
        meet_no = event.params["meetNo"]
        se.index(f"{models.MEETING_COLLECT}/{meet_no}", search_client.DocType.MEETING)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Failed when updating meeting. {event.params}") from e


@firestore_fn.on_document_created(
    document="meetings/{meetNo}/files/{fileNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.MB_512,
)
def on_meeting_file_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
):
    try:
        _index_meeting_file(event)
    except Exception as e:
        logger.error(f"Fail on meeting file create: {event.params}")
        raise RuntimeError(f"Fail on meeting file create: {event.params}") from e


@firestore_fn.on_document_updated(
    document="meetings/{meetNo}/files/{fileNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.GB_1,
)
def on_meeting_file_update(
    event: firestore_fn.Event[
        firestore_fn.Change[firestore_fn.DocumentSnapshot | None]
    ],
):
    try:
        _update_meeting_file_embeddings(event)
        _index_meeting_file(event)
    except Exception as e:
        logger.error(f"Fail on meeting file update {event.params}")
        raise RuntimeError("Fail on meeting file update") from e


def _index_meeting_file(event: firestore_fn.Event):
    """Index the meeting file."""
    se = search_client.DocumentSearchEngine.create(api_key=TYPESENSE_API_KEY.value)
    meet_no = event.params["meetNo"]
    file_no = event.params["fileNo"]
    se.index(
        f"{models.MEETING_COLLECT}/{meet_no}/{models.FILE_COLLECT}/{file_no}",
        search_client.DocType.MEETING_FILE,
    )


def _update_meeting_file_embeddings(
    event: firestore_fn.Event[
        firestore_fn.Change[firestore_fn.DocumentSnapshot | None]
    ],
):
    meet_no = event.params["meetNo"]
    file_no = event.params["fileNo"]
    doc_path = f"{models.MEETING_COLLECT}/{meet_no}/{models.FILE_COLLECT}/{file_no}"
    before: models.MeetingFile | None
    after: models.MeetingFile | None
    if event.data.before:
        before = models.MeetingFile.from_dict(event.data.before.to_dict())
    if event.data.after:
        after = models.MeetingFile.from_dict(event.data.after.to_dict())

    if after and (not before or after.full_text != before.full_text):
        q = tasks.CloudRunQueue.open("updateDocumentEmbeddings")
        q.run(doc_path=doc_path, group=models.FILE_COLLECT)


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=300),
    rate_limits=RateLimits(max_concurrent_dispatches=20),
    region=_REGION,
    timeout_sec=300,
    memory=MemoryOption.MB_512,
)
def fetchMeetingFromWeb(request: tasks_fn.CallableRequest):
    """Fetch the meeting from the web."""
    try:
        _fetch_meeting_from_web(request)
    except Exception as e:
        logging.exception(e)
        raise RuntimeError(f"Error fetching meeting: {request.data}") from e


def _fetch_meeting_from_web(request: tasks_fn.CallableRequest):
    logger.debug(f"Fetch meeting from web: {request.data}")
    meet_no = request.data["meetNo"]
    url = request.data["url"]
    db = firestore.client()
    meet_doc_ref = db.collection(models.MEETING_COLLECT).document(meet_no)
    meet_doc = meet_doc_ref.get()
    meet: models.Meeting | None = None
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

    ivods: list[models.IVOD] = []
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
    document="meetings/{meetNo}/proceedings/{billNo}",
    region=_REGION,
    memory=MemoryOption.MB_512,
)
def on_meeting_proceedings_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
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
    memory=MemoryOption.MB_512,
)
def fetchProceedingFromWeb(request: tasks_fn.CallableRequest):
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
        if meet.meeting_date_start.replace(tzinfo=None) < created_date.replace(
            tzinfo=None
        ):
            created_date = meet.meeting_date_start
    return created_date


def _fetch_proceeding_from_web(request: tasks_fn.CallableRequest):
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
        proc.related_bills = [bill.bill_no for bill in related_bills]

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
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
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
    attach.last_update_time = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    ref.update(attach.asdict())


@firestore_fn.on_document_created(
    document="meetings/{meetNo}/files/{fileNo}",
    region=_REGION,
    memory=MemoryOption.GB_2,
)
def on_meetings_attached_file_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
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
    memory=MemoryOption.MB_512,
)
def fetchIVODFromWeb(request: tasks_fn.CallableRequest):
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

    videos = [models.Video(url=v.url, hd_url=v.hd_url) for v in r.get_videos()]
    speeches = [
        models.Video(url=v.url, hd_url=v.hd_url, member=v.member)
        for v in r.get_member_speeches()
    ]

    batch = db.batch()
    update_keys = ["url", "hd_url", "member"]

    for v in videos:
        batch.set(
            ref.collection(models.VIDEO_COLLECT).document(v.document_id),
            {k: v for k, v in v.asdict().items() if k in update_keys},
            merge=True,
        )

    for v in speeches:
        batch.set(
            ref.collection(models.SPEECH_COLLECT).document(v.document_id),
            {k: v for k, v in v.asdict().items() if k in update_keys},
            merge=True,
        )
    batch.commit()


@firestore_fn.on_document_created(
    document="meetings/{meetNo}/ivods/{ivodNo}",
    region=_REGION,
    memory=MemoryOption.MB_512,
)
def on_meeting_ivod_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
):
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
def downloadVideo(request: tasks_fn.CallableRequest):
    """Handler on download video."""
    try:
        meet_no = request.data["meetNo"]
        ivod_no = request.data["ivodNo"]
        video_no = request.data["videoNo"]

        db = firestore.client()
        ivod_ref = db.document(
            f"{models.MEETING_COLLECT}/{meet_no}/{models.IVOD_COLLECT}/{ivod_no}"
        )
        if not ivod_ref.get().exists:
            logger.warn(f"IVOD {ivod_ref.path} doesn't exist.")
            return

        doc_path = _download_video(ivod_ref, video_no)
        if not doc_path:
            logger.warn(f"Fail to download video {request.data}, skip extracting audio")
            return
        q = tasks.CloudRunQueue.open("extractAudio")
        q.run(path=doc_path)
        # TODO: enable download HD video after we get budget.
        hdq = tasks.CloudRunQueue.open("downloadHdVideo")
        hdq.run(meet_no=meet_no, ivod_no=ivod_no, video_no=video_no)
    except Exception as e:
        logger.error(f"fail to download video: {e}")
        raise RuntimeError(f"Error downloading video: {request.data}") from e


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=600),
    rate_limits=RateLimits(max_concurrent_dispatches=20),
    cpu=2,
    memory=MemoryOption.MB_512,
    region=_REGION,
    timeout_sec=1800,
    max_instances=30,
    concurrency=2,
)
def downloadHdVideo(request: tasks_fn.CallableRequest):
    try:
        meet_no = request.data["meetNo"]
        ivod_no = request.data["ivodNo"]
        video_no = request.data["videoNo"]

        db = firestore.client()
        ivod_ref = db.document(
            f"{models.MEETING_COLLECT}/{meet_no}/{models.IVOD_COLLECT}/{ivod_no}"
        )
        if not ivod_ref.get().exists:
            logger.warn(f"IVOD {ivod_ref.path} doesn't exist.")
            return

        doc_path = _download_video(ivod_ref, video_no, download_hd=True)
        if not doc_path:
            logger.warn(f"Fail to download HD video {request.data}")
            return
    except Exception as e:
        logger.error(f"fail to download HD video: {e}")
        raise RuntimeError(f"Error downloading HD video: {request.data}") from e


def _download_video(
    ivod_ref: document.DocumentReference, video_no: str, download_hd: bool = False
) -> str | None:
    """
    Return: firestore path to the updated video.
    """
    video_ref, collect = _find_video_in_ivod(ivod_ref, video_no)
    if not video_ref:
        return None

    speech_count = video_ref.collection(models.SPEECH_COLLECT).count().get()[0][0].value
    if collect == models.VIDEO_COLLECT and speech_count > 0:
        return None
    elif download_hd and collect != models.SPEECH_COLLECT:
        logger.warn("Downloading HD video only supports speech collection.")
        return None

    video: models.Video = models.Video.from_dict(video_ref.get().to_dict())

    url = video.hd_url if download_hd else video.url

    if not url:
        raise RuntimeError("Can't find video URL.")

    logger.debug(f"Open video: {url}")
    r = readers.VideoReader.open(url)

    if r.meta.duration > dt.timedelta(hours=3):
        logger.warn("Video %s is too long. (> 3 hours)", url)
        return None
    elif r.meta.duration <= dt.timedelta.min:
        logger.warn("Video %s doesn't have duration info, skip it.", url)
        return None
    logger.debug(f"Prepare to download video: {url}")

    clips = []
    temp_mp4 = []
    bucket = storage.bucket()
    folder = "hd_clips" if download_hd else "clips"

    def _upload_clip(i: int) -> str:
        blob = bucket.blob(f"videos/{video.document_id}/{folder}/{i}.mp4")
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

    if not download_hd:
        for i in range(min(r.clips_count, 10)):
            # Safe guarded, prevent downloading too many chunks.
            clips.append(_upload_clip(i))
    else:
        logger.warn("Skip download HD videos.")

    update_keys: list[str]
    if download_hd:
        video.hd_playlist = r.playlist_url or ""
        if clips:
            video.hd_clips = clips
        update_keys = ["hd_playlist", "hd_clips"]
    else:
        video.playlist = r.playlist_url or ""
        video.start_time = r.meta.start_time
        if clips:
            video.clips = clips
        update_keys = ["playlist", "clips", "start_time"]

    video_ref.update({k: v for k, v in video.asdict().items() if k in update_keys})
    for mp4 in temp_mp4:
        os.remove(mp4)
    return video_ref.path


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
    document="meetings/{meetNo}/ivods/{ivodNo}/{videoCollect}/{videoNo}",
    region=_REGION,
    memory=MemoryOption.MB_512,
)
def on_ivod_video_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
):
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


@firestore_fn.on_document_created(
    document="proceedings/{procNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.MB_512,
)
def on_proceeding_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
):
    try:
        proc_no = event.params["procNo"]
        se = search_client.DocumentSearchEngine.create(api_key=TYPESENSE_API_KEY.value)
        se.index(
            f"{models.PROCEEDING_COLLECT}/{proc_no}", search_client.DocType.PROCEEDING
        )
    except Exception as e:
        logger.error(f"Fail on_proceeding_create: {event.params}")
        raise RuntimeError(f"Fail on_proceeding_create: {event.params}") from e


@firestore_fn.on_document_updated(
    document="proceedings/{procNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.MB_512,
)
def on_proceeding_update(
    event: firestore_fn.Event[
        firestore_fn.Change[firestore_fn.DocumentSnapshot | None]
    ],
):
    try:
        proc_no = event.params["procNo"]
        se = search_client.DocumentSearchEngine.create(api_key=TYPESENSE_API_KEY.value)
        se.index(
            f"{models.PROCEEDING_COLLECT}/{proc_no}", search_client.DocType.PROCEEDING
        )
    except Exception as e:
        logger.error("Fail on_proceeding_update: %s", event.params)
        raise RuntimeError(f"Fail on_proceeding_update: {event.params}") from e


@firestore_fn.on_document_created(
    document="proceedings/{procNo}/attachments/{attachNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.MB_512,
)
def on_proceeding_attachment_create(
    event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
):
    try:
        _index_proceeding_attachment(event)
    except Exception as e:
        logger.error(f"Fail on_proceeding_attachment_create: {event.params}")
        raise RuntimeError(
            f"Fail on_proceeding_attachment_create: {event.params}"
        ) from e


@firestore_fn.on_document_updated(
    document="proceedings/{procNo}/attachments/{attachNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.MB_512,
)
def on_proceeding_attachment_update(
    event: firestore_fn.Event[
        firestore_fn.Change[firestore_fn.DocumentSnapshot | None]
    ],
):
    try:
        _update_proceeding_attachment_embeddings(event)
        _index_proceeding_attachment(event)
    except Exception as e:
        logger.error(f"Fail on_proceeding_attachment_update: {event.params}")
        raise RuntimeError(
            f"Fail on_proceeding_attachment_update: {event.params}"
        ) from e


def _index_proceeding_attachment(event: firestore_fn.Event):
    proc_no = event.params["procNo"]
    attach_no = event.params["attachNo"]
    se = search_client.DocumentSearchEngine.create(api_key=TYPESENSE_API_KEY.value)
    se.index(
        f"{models.PROCEEDING_COLLECT}/{proc_no}/{models.ATTACH_COLLECT}/{attach_no}",
        search_client.DocType.ATTACHMENT,
    )


def _update_proceeding_attachment_embeddings(
    event: firestore_fn.Event[
        firestore_fn.Change[firestore_fn.DocumentSnapshot | None]
    ],
):
    proc_no = event.params["procNo"]
    attach_no = event.params["attachNo"]
    doc_path = (
        f"{models.PROCEEDING_COLLECT}/{proc_no}/" f"{models.ATTACH_COLLECT}/{attach_no}"
    )

    before: models.Attachment | None
    after: models.Attachment | None
    if event.data.before:
        before = models.Attachment.from_dict(event.data.before.to_dict())
    if event.data.after:
        after = models.Attachment.from_dict(event.data.after.to_dict())

    if after and (not before or after.full_text != before.full_text):
        q = tasks.CloudRunQueue.open("updateDocumentEmbeddings")
        q.run(doc_path=doc_path, group=models.ATTACH_COLLECT)


@firestore_fn.on_document_updated(
    document="meetings/{meetNo}/ivods/{videoNo}/speeches/{speechNo}",
    region=_REGION,
    secrets=[TYPESENSE_API_KEY],
    memory=MemoryOption.MB_512,
)
def on_speech_update(
    event: firestore_fn.Event[
        firestore_fn.Change[firestore_fn.DocumentSnapshot | None]
    ],
):
    try:
        meet_no = event.params["meetNo"]
        video_no = event.params["videoNo"]
        speech_no = event.params["speechNo"]
        doc_path = (
            f"{models.MEETING_COLLECT}/{meet_no}/"
            f"{models.IVOD_COLLECT}/{video_no}/"
            f"{models.SPEECH_COLLECT}/{speech_no}"
        )

        before: models.Video | None
        after: models.Video | None
        if event.data.before:
            before = models.Video.from_dict(event.data.before.to_dict())
        if event.data.after:
            after = models.Video.from_dict(event.data.after.to_dict())

        # Update embeddings
        if after and (not before or after.transcript != before.transcript):
            q = tasks.CloudRunQueue.open("updateDocumentEmbeddings")
            q.run(doc_path=doc_path, group=models.SPEECH_COLLECT)

        _index_speech(doc_path)
    except Exception as e:
        logger.error(f"Fail on_speech_update: {event.params}")
        raise RuntimeError(f"Fail on_speech_update: {event.params}") from e


def _index_speech(doc_path: str):
    se = search_client.DocumentSearchEngine.create(api_key=TYPESENSE_API_KEY.value)
    se.index(doc_path, search_client.DocType.VIDEO)


@https_fn.on_request(region=_REGION, memory=MemoryOption.MB_512)
def update_legislators(request: https_fn.Request) -> https_fn.Response:
    term = request.args.get("term", type=int)
    res = session.new_legacy_session().get(
        LEGISLATURE_LEGISLATOR_INFO_API.value,
        headers=session.REQUEST_HEADER,
        params={"term": term, "fileType": "json"},
        timeout=_DEFAULT_TIMEOUT,
    )
    if res.status_code != 200:
        logger.error(f"Error getting meetSings: {res.status_code}")
        return https_fn.Response(
            json.dumps(
                {
                    "error": "Error getting legislators.",
                    "term": term,
                }
            ),
            status=res.status_code,
            content_type="application/json",
        )
    db = firestore.client()
    batch = db.batch()
    data: dict = json.loads(res.text)
    member: dict[str, Any]
    for member in data.get("dataList", []):
        onboard_date = dt.datetime.strptime(member.get("onboardDate", ""), "%Y/%m/%d")
        term = member.get("term", None)
        m = models.Legislator(
            name=member.get("name", ""),
            ename=member.get("ename", ""),
            sex=member.get("sex", ""),
            party=member.get("party", ""),
            area=member.get("areaName", ""),
            onboard_date=onboard_date,
            degree=member.get("degree", ""),
            avatar=member.get("picUrl", ""),
            leave=member.get("leaveFlag", "") == "是",
            terms=[term] if term is not None else [],
        )
        doc_ref = db.collection(models.MEMBER_COLLECT).document(m.document_id)
        doc = doc_ref.get()
        if doc.exists:
            old_m = models.Legislator.from_dict(doc.to_dict())
            m.terms = sorted(list(set(m.terms + old_m.terms)))
            batch.update(doc_ref, m.asdict())
            continue
        batch.set(doc_ref, m.asdict())
    batch.commit()

    return https_fn.Response(
        json.dumps({}),
        status=200,
        content_type="application/json",
    )


@https_fn.on_request(region=_REGION, memory=MemoryOption.MB_512)
def update_meetings_by_date(request: https_fn.Request):
    try:
        meet_date = request.args.get("date", "")
        term = int(request.args.get("term", 0))
        period = int(request.args.get("period", 0))
        if not meet_date:
            return https_fn.Response("date is required.", status=400)
        meetings = _update_meeting_by_date(meet_date, term=term, period=period)
        return https_fn.Response(json.dumps({"meetings": meetings}), status=200)
    except Exception as e:
        logger.error(f"Fail to update meeting by date: {e}")
        raise RuntimeError(f"Fail to update meeting by date: {e}") from e


def _update_meeting_by_date(
    meet_date: str, term: int = 0, period: int = 0
) -> list[str]:
    res = session.new_legacy_session().get(
        LEGISLATURE_PPG_API.value + "/v1/all-sittings",
        params={"size": -1, "page": 1, "meetingDate": meet_date},
        headers=session.REQUEST_HEADER,
        timeout=_DEFAULT_TIMEOUT,
    )
    if not res.ok:
        raise RuntimeError(f"Fail to get meeting by {meet_date}: {res.text}")

    db = firestore.client()
    batch = db.batch()
    items = res.json().get("items", [])
    item: dict[str, Any]
    new_meetings = []
    for item in items:
        meeting_no = item.get("id", "")
        meeting_date = item.get("meetingDate", "")
        meeting_time = item.get("meetingTime", "")
        if not meeting_no or not meeting_date or not meeting_time:
            continue
        m = models.Meeting(
            meeting_no=meeting_no,
            meeting_name=item.get("meetingName", ""),
            meeting_content=item.get("title", ""),
            meeting_date_desc=f"{meet_date} {meeting_time}",
            meeting_unit=item.get("meetingUnit", ""),
            term=term,
            session_period=period,
        )
        ref = db.collection(models.MEETING_COLLECT).document(m.document_id)
        if ref.get().exists:
            continue
        new_meetings.append(m.meeting_no)
        batch.set(ref, m.asdict())
    batch.commit()
    return new_meetings


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=600),
    rate_limits=RateLimits(max_concurrent_dispatches=300),
    memory=MemoryOption.MB_512,
    region=_REGION,
    timeout_sec=1800,
    max_instances=30,
    concurrency=10,
)
def updateDocumentEmbeddings(request: tasks_fn.CallableRequest):
    doc_path = request.data["docPath"]
    group = request.data["group"]

    db = firestore.client()
    ref = db.document(doc_path)
    doc = ref.get()
    if not doc.exists:
        logger.warn(f"Document {doc_path} doesn't exist.")
        return

    text = _get_document_full_text(doc, group)
    if not text:
        return

    text_embeddings = embeddings.get_embeddings_from_text(text)
    models.update_embeddings(ref, text_embeddings)


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=600),
    rate_limits=RateLimits(max_concurrent_dispatches=300),
    memory=MemoryOption.MB_512,
    region=_REGION,
    timeout_sec=1800,
    max_instances=30,
    concurrency=10,
)
def updateDocumentHashtags(request: tasks_fn.CallableRequest):
    doc_path = request.data["docPath"]
    group = request.data["group"]

    db = firestore.client()
    ref = db.document(doc_path)
    doc = ref.get()
    if not doc.exists:
        logger.warn(f"Document {doc_path} doesn't exist.")
        return

    text = _get_document_full_text(doc, group)
    if not text:
        return
    summary = gemini.HashTagsSummaryQuery(doc_path=doc_path, content=text).run(
        gemini.HashTagsSummary
    )
    if not summary:
        return
    m = models.FireStoreDocument.from_dict(doc.to_dict())
    m.has_hash_tags = bool(summary.tags)
    m.hash_tags_summarized_at = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    m.hash_tags = summary.tags
    ref.update(m.asdict())


def _get_document_full_text(doc: document.DocumentSnapshot, group) -> str | None:
    """Get the full text of the document.

    The full text is usually the content with most information of the document.
    For example, the transcript of a video, the full text of an attachment.
    """
    doc_path = doc.reference.path
    match group:
        case models.SPEECH_COLLECT:
            video = models.Video.from_dict(doc.to_dict())
            if not video.transcript or not video.has_transcript:
                logger.warn(f"Video {doc_path} doesn't have transcript.")
                return None
            return video.transcript
        case models.ATTACH_COLLECT | models.FILE_COLLECT:
            attach = models.Attachment.from_dict(doc.to_dict())
            if not attach.full_text:
                logger.warn(f"Attach {doc_path} doesn't have full text.")
                return None
            return attach.full_text
        case _:
            raise TypeError(f"Unknown group: {group}")
