"""Legislature parser."""

import datetime as dt
import json
import logging

import requests
import utils
from firebase_admin import firestore, functions
from firebase_functions import firestore_fn, https_fn, logger, tasks_fn
from firebase_functions.options import RateLimits, RetryConfig
from legislature import LEGISLATURE_MEETING_INFO_API, models, readers
from params import DEFAULT_TIMEOUT_SEC
from utils import testings

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


@https_fn.on_request()
def update_meetings(request: https_fn.Request) -> https_fn.Response:
    """
    Update the meetings in the database.

    Args:
        term (str): The term to update the meetings for.
    """
    logger.log("Updating meetings")
    term = request.args.get("term", type=int)
    logger.debug(f"Term: {term}")
    res = requests.get(
        LEGISLATURE_MEETING_INFO_API.value,
        headers=_REQUEST_HEADEER,
        params={"term": term, "fileType": "json"},
        timeout=_DEFAULT_TIMEOUT,
        verify=False,
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
    collecion = db.collection("meetings")
    count = 0
    for m in data.get("dataList", []):
        try:
            meet: models.Meeting = models.Meeting.from_dict(m)
            if not meet.document_id:
                continue
            doc_ref = collecion.document(meet.document_id)
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


@firestore_fn.on_document_created(document="meetings/{meetNo}")
def fetch_meeting_when_created(
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
    meet_no = event.params["meetNo"]
    meet_ref = db.collection("meetings").document(meet_no)
    meet_doc = meet_ref.get()
    if not meet_doc.exists:
        raise RuntimeError(f"Meeting {meet_no} does not exist.")
    meet: models.Meeting = models.Meeting.from_dict(meet_doc.to_dict())
    q = FetchMeetingFromWebQueue()
    q.run(meet_no, meet.get_url())


class FetchMeetingFromWebQueue:
    """Fetch the meeting from the web."""

    def __init__(self):
        self.queue = functions.task_queue("fetch_meeting_from_web")
        self.target = utils.get_function_url("fetch_meeting_from_web")
        self.option = functions.TaskOptions(
            dispatch_deadline_seconds=1800, uri=self.target
        )

    @testings.skip_when_using_emulators
    def run(self, meet_no: str, url: str):
        """run the task."""
        self.queue.enqueue({"data": {"meetNo": meet_no, "url": url}}, self.option)


@tasks_fn.on_task_dispatched(
    retry_config=RetryConfig(max_attempts=3, max_backoff_seconds=300),
    rate_limits=RateLimits(max_concurrent_dispatches=20),
)
def fetch_meeting_from_web(request: tasks_fn.CallableRequest) -> any:
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
    meet_doc_ref = db.collection("meetings").document(meet_no)
    meet_doc = meet_doc_ref.get()
    meet: models.Meeting = None
    if meet_doc.exists:
        meet = models.Meeting.from_dict(meet_doc.to_dict())
    else:
        meet = models.Meeting.from_dict({"meetingNo": meet_no})
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

    videos = [models.IVOD(name=v.name, url=v.url) for v in r.get_videos()]
    meeting_files = [
        models.MeetingFile(name=a.name, url=a.url)
        for a in r.get_files(allow_download=True)
    ]
    proceedings = [
        models.Proceeding(name=p.name, url=p.url, bill_no=p.bill_no)
        for p in r.get_related_proceedings()
    ]

    meet_doc_ref.update(meet.asdict())

    videos_collect = meet_doc_ref.collection("videos")
    for v in videos:
        videos_collect.document(v.document_id).set(v.asdict(), merge=True)

    files_collect = meet_doc_ref.collection("files")
    for f in meeting_files:
        files_collect.document(f.document_id).set(f.asdict(), merge=True)

    proceedings_collect = meet_doc_ref.collection("proceedings")
    for p in proceedings:
        proceedings_collect.document(p.document_id).set(p.asdict(), merge=True)
