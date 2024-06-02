"""Legislature parser."""

import json

import requests
from firebase_admin import firestore
from firebase_functions import https_fn, logger
from legislature import LEGISLATURE_MEETING_INFO_API, models
from params import DEFAULT_TIMEOUT_SEC

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
