import unittest

import requests  # type: ignore
import utils
from firebase_admin import firestore, storage  # type: ignore
from legislature import models
import utils
from utils import testings
import pathlib
import uuid


def _test_file(name: str) -> pathlib.Path:
    return pathlib.Path(__file__).parent / "testdata" / name


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


@testings.disable_background_triggers
def test_extract_audio_task():
    db = firestore.client()
    bucket = storage.bucket()
    mp4 = _test_file("clip.mp4")
    uid = uuid.uuid4().hex
    blob = bucket.blob(f"videos/{uid}/clips/0.mp4")
    with mp4.open("rb") as f:
        blob.upload_from_file(f)
    gs_path = f"gs://{bucket.name}/{blob.name}"
    meet = db.collection(models.MEETING_COLLECT).document()
    meet.set({})
    ivod = meet.collection(models.IVOD_COLLECT).document()
    ivod.set({})
    speech = ivod.collection(models.SPEECH_COLLECT).document()
    v = models.Video(clips=[gs_path])
    speech.set(v.asdict())
    url = utils.get_function_url("extractAudio")
    res = requests.post(
        url,
        json={"data": {"path": speech.path}},
        headers={"content-type": "application/json"},
        timeout=120,
    )
    assert res.ok, res.text

    def is_ready():
        doc = speech.get()
        v = models.Video.from_dict(doc.to_dict())
        return v.audios

    testings.wait_until(is_ready, timeout=120)
