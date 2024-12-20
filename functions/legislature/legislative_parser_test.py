"""
Test for legislative_parser.py
"""

# pylint: disable=missing-function-docstring
import unittest
from unittest import mock

import requests  # type: ignore
import search.client as search_client
import utils
from firebase_admin import firestore, storage  # type: ignore
from google.cloud.firestore import DocumentReference  # type: ignore
from legislature import models
from search import testing as search_testing
from utils import tasks, testings
from legislature import legislative_parser


# fetch_meeting_from_web
class TestFetchMeetingFromWeb(unittest.TestCase):
    """
    Test for fetch_meeting_from_web
    """

    def setUp(self):
        super().setUp()
        self.db = firestore.client()

    @testings.skip_when_no_network
    @testings.require_firestore_emulator
    @testings.disable_background_triggers
    def test_fetch_meeting_from_web(self):
        m = models.Meeting.from_dict(
            {
                "term": "11",
                "sessionPeriod": "0 ",
                "sessionTimes": "0 ",
                "meetingTimes": "null",
                "meetingNo": "2024013195",
                "meetingDateDesc": "113/02/01 08:00-17:00",
                "meetingRoom": "議場",
                "meetingUnit": "院會",
                "jointCommittee": "",
                "meetingName": "第11屆立法院預備會議",
                "meetingContent": "第11屆立法委員報到、就職宣誓暨院長、副院長選舉及就職宣誓",
                "coChairman": "",
                "attendLegislator": "丁學忠",
                "selectTerm": "all",
            }
        )
        doc_ref = self.db.collection("meetings").document(m.meeting_no)
        doc_ref.set(m.asdict())

        url = utils.get_function_url("fetchMeetingFromWeb")
        res = requests.post(
            url,
            json={"data": {"meetNo": m.meeting_no, "url": m.get_url()}},
            headers={"content-type": "application/json"},
            timeout=60,
        )
        videos = list(
            self.db.collection("meetings")
            .document(m.meeting_no)
            .collection("ivods")
            .stream()
        )

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(len(videos), 1)


class TestFetchProceedingFromWeb(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.db = firestore.client()

    @testings.skip_when_no_network
    @testings.require_firestore_emulator
    @testings.disable_background_triggers
    def test_fetch_proceeding_from_web_not_exist(self):
        url = utils.get_function_url("fetchProceedingFromWeb")

        requests.post(
            url,
            json={
                "data": {
                    "billNo": "202110044210000",
                    "url": "https://ppg.ly.gov.tw/ppg/bills/202110044210000/details",
                }
            },
            headers={"content-type": "application/json"},
            timeout=60,
        )

        doc_ref = self.db.document(f"{models.PROCEEDING_COLLECT}/202110044210000")
        attachs = list(doc_ref.collection(models.ATTACH_COLLECT).stream())
        assert len(attachs) == 2

    @testings.disable_background_triggers
    def test_fetch_proceeding_from_web_with_related_bills(self):
        url = utils.get_function_url("fetchProceedingFromWeb")

        requests.post(
            url,
            json={
                "data": {
                    "billNo": "202110006550000",
                    "url": "https://ppg.ly.gov.tw/ppg/bills/202110006550000/details",
                }
            },
            headers={"content-type": "application/json"},
            timeout=60,
        )

        doc_ref = self.db.document(f"{models.PROCEEDING_COLLECT}/202110006550000")
        doc = doc_ref.get()
        assert doc.exists
        m = models.Proceeding.from_dict(doc.to_dict())
        assert len(m.related_bills) == 4

        attachs = list(doc_ref.collection(models.ATTACH_COLLECT).stream())
        assert len(attachs) == 2


@unittest.skip("manul test")
@testings.skip_when_no_network
def test_fetch_meeting_from_web_e2e():
    m = models.Meeting.from_dict(
        {
            "meetingNo": "2024053177",
            "meetingDateDesc": "113/06/05 09:00-17:30",
        }
    )
    db = firestore.client()
    ref = db.collection("meetings").document(m.meeting_no)
    ref.set(m.asdict())


@testings.skip_when_no_network
def test_create_proceeding_e2e():
    url = utils.get_function_url("fetchProceedingFromWeb")
    requests.post(
        url,
        json={
            "data": {
                "billNo": "202110051530000",
                "url": "https://ppg.ly.gov.tw/ppg/bills/202110051530000/details",
            }
        },
        headers={"content-type": "application/json"},
        timeout=120,
    )
    db = firestore.client()
    p = f"{models.PROCEEDING_COLLECT}/202110051530000/{models.ATTACH_COLLECT}"
    testings.wait_until(lambda: len(list(db.collection(p).stream())) > 0)
    attachs = db.collection(p).where("name", "==", "關係文書PDF").limit(1).get()
    assert len(attachs) == 1
    attach = attachs[0]

    def check_attach_text():
        doc = attach.reference.get()
        m = models.Attachment.from_dict(doc.to_dict())
        return "委員 提案第 11005153 號" in m.full_text

    testings.wait_until(check_attach_text, timeout=20)


@testings.skip_when_no_network
@testings.require_firestore_emulator
@testings.disable_background_triggers
def test_download_video():
    db = firestore.client()
    meet_ref = db.collection(models.MEETING_COLLECT).document()
    meet_ref.set({})
    ivod_ref = meet_ref.collection(models.IVOD_COLLECT).document()
    ivod_ref.set({})
    video = models.Video(url="https://ivod.ly.gov.tw/Play/Clip/300K/152612")
    video_ref = ivod_ref.collection(models.VIDEO_COLLECT).document(video.document_id)
    video_ref.set(video.asdict())
    url = utils.get_function_url("downloadVideo")
    requests.post(
        url,
        json={
            "data": {
                "meetNo": meet_ref.id,
                "ivodNo": ivod_ref.id,
                "videoNo": video_ref.id,
            }
        },
        headers={"content-type": "application/json"},
        timeout=360,
    )
    video = models.Video.from_dict(video_ref.get().to_dict())
    assert len(video.clips) == 1
    bucket = storage.bucket()
    assert bucket.blob(video.clips[0]).exists


@testings.skip_when_no_network
@testings.require_firestore_emulator
@testings.disable_background_triggers
def test_download_hd_video():
    db = firestore.client()
    meet_ref = db.collection(models.MEETING_COLLECT).document()
    meet_ref.set({})
    ivod_ref = meet_ref.collection(models.IVOD_COLLECT).document()
    ivod_ref.set({})
    video = models.Video(
        url="https://ivod.ly.gov.tw/Play/Clip/300K/152612",
        hd_url="https://ivod.ly.gov.tw/Play/Clip/1M/152612",
    )
    video_ref = ivod_ref.collection(models.SPEECH_COLLECT).document(video.document_id)
    video_ref.set(video.asdict())
    url = utils.get_function_url("downloadHdVideo")
    requests.post(
        url,
        json={
            "data": {
                "meetNo": meet_ref.id,
                "ivodNo": ivod_ref.id,
                "videoNo": video_ref.id,
            }
        },
        headers={"content-type": "application/json"},
        timeout=360,
    )
    video = models.Video.from_dict(video_ref.get().to_dict())
    assert len(video.hd_clips) == 0
    assert video.hd_playlist != ""


@testings.skip_when_no_network
def test_on_ivod_video_create():
    db = firestore.client()

    @testings.disable_background_triggers
    def init():
        meet_ref = db.collection(models.MEETING_COLLECT).document()
        meet_ref.set({})
        ivod_ref = meet_ref.collection(models.IVOD_COLLECT).document()
        ivod_ref.set({})
        return ivod_ref

    ivod_ref = init()
    video = models.Video(url="https://ivod.ly.gov.tw/Play/Clip/300K/152575")
    video_ref = ivod_ref.collection(models.VIDEO_COLLECT).document(video.document_id)
    video_ref.set(video.asdict())

    def check_blob_exist():
        video = models.Video.from_dict(video_ref.get().to_dict())
        if len(video.clips) == 0:
            return False
        bucket = storage.bucket()
        return bucket.blob(video.clips[0]).exists

    testings.wait_until(
        check_blob_exist, timeout=120, message="Fail to download video."
    )


@search_testing.initialize_search_engine
def test_on_meeting_update_create_index():
    db = firestore.client()

    @testings.disable_background_triggers
    def init() -> DocumentReference:
        ref = db.collection(models.MEETING_COLLECT).document()
        ref.set({})
        return ref

    ref = init()
    ref.update({"ai_summary": ref.id})

    def document_indexed() -> bool:
        client = search_client.DocumentSearchEngine.create("xyz")
        res = client.query(ref.id)
        return res.hit_count > 0

    testings.wait_until(
        document_indexed, timeout=10, message="Fail to create document index."
    )


@search_testing.initialize_search_engine
def test_on_meeting_file_update_index():
    db = firestore.client()
    se = search_client.DocumentSearchEngine.create("xyz")

    @testings.disable_background_triggers
    def init() -> DocumentReference:
        meet_ref = db.collection(models.MEETING_COLLECT).document()
        meet_ref.set({})
        file_ref = meet_ref.collection(models.FILE_COLLECT).document()
        file_ref.set({})
        return file_ref

    file_ref = init()
    assert se.query("document").hit_count == 0
    file_ref.update({"ai_summary": "document"})
    testings.wait_until(lambda: se.query("document").hit_count == 1)


def test_update_legislators():
    url = utils.get_function_url("update_legislators")

    res = requests.get(url, params={"term": 11}, timeout=30)

    assert res.ok


@testings.skip_when_no_network
@testings.require_firestore_emulator
@testings.disable_background_triggers
def test_update_meetings_by_date():
    url = utils.get_function_url("update_meetings_by_date")
    res = requests.get(url, params={"date": "113/04/24"}, timeout=30)
    # TODO: check the result
    assert res.ok


class TestGetMeetingAtDate(unittest.TestCase):

    @mock.patch.object(legislative_parser.session, "new_legacy_session")
    def test_get_meeting_at_date(self, mock_new_legacy_session: mock.Mock):
        mock_response = mock.MagicMock(spec=requests.Response)
        mock_session = mock_new_legacy_session.return_value
        mock_session.get.return_value = mock_response
        mock_response.ok = True
        mock_response.json.return_value = {
            "totalItems": 1,
            "totalPages": 1,
            "currentPage": 0,
            "items": [
                {
                    "id": "2024112922",
                    "title": "title",
                    "content": "內政 09:00-17:30",
                    "content2": "召集人：徐欣瑩委員",
                    "location": "紅樓202會議室",
                    "tags": ["113年12月05日"],
                    "tags2": [],
                    "attachments": [],
                    "meetingDate": "113/12/05",
                    "meetingName": "立法院第11屆第2會期內政委員會第14次全體委員會議",
                    "meetingUnit": "內政",
                    "meetingTime": "09:00-17:30",
                },
            ],
        }

        meetings = legislative_parser.get_meetings_at_date("113/12/05")

        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0].meeting_no, "2024112922")
        self.assertEqual(meetings[0].meeting_date_desc, "113/12/05 09:00-17:30")
        self.assertEqual(meetings[0].term, 11)


@testings.require_firestore_emulator
@testings.skip_when_no_network
def test_update_video_embeddings():
    doc_path = "meetings/2024030180/ivods/00084705648089667888/speeches/ba63d8c8ec393d1787165f85fd0ceb9d"
    q = tasks.CloudRunQueue.open("updateDocumentEmbeddings")
    q.run(doc_path=doc_path, group=models.SPEECH_COLLECT)

    db = firestore.client()
    ref = db.document(doc_path)
    embeddings = models.get_embeddings(ref)

    assert len(embeddings) > 0


if __name__ == "__main__":
    unittest.main()
