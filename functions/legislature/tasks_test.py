import unittest

import requests  # type: ignore
import utils
from firebase_admin import firestore  # type: ignore
from legislature import models
from utils import testings


@unittest.skip("manual test only")
@testings.skip_when_no_network
@testings.disable_background_triggers
def test_summarize_video_task():
    db = firestore.client()
    speech_ref = db.document(
        "meetings/2024030699/ivods/00748465571603743750/speeches/0089757e842c31968a8bd475f9ccd1d4"
    )
    ivod_ref = db.document("meetings/2024030699/ivods/00748465571603743750")
    target_ref = ivod_ref.collection(models.SPEECH_COLLECT).document()
    target_ref.set(speech_ref.get().to_dict())
    url = utils.get_function_url("summarizeVideo")
    requests.post(
        url,
        json={"data": {"path": target_ref.path}},
        headers={"content-type": "application/json"},
        timeout=120,
    )

    def is_ready():
        target_doc = target_ref.get()
        v = models.Video.from_dict(target_doc.to_dict())
        return v.ai_summarized and v.ai_summary

    testings.wait_until(is_ready, timeout=120)
