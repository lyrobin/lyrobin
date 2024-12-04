import unittest
import uuid
from unittest import mock
import datetime as dt
from typing import Any

from legislature import models
from search import client as search_client
from firebase_admin import firestore  # type: ignore


class ClientTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.mock_client = mock.MagicMock()
        se = search_client.DocumentSearchEngine.create(api_key="xyz")
        se.drop_collection(collection="documents")
        se.drop_collection(collection="documents_v2")
        se.initialize_collections()

    def _mock_doc(self, m: models.FireStoreDocument, doc_path: str):
        mock_ref = self.mock_client.document.return_value
        mock_doc = mock_ref.get()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = m.asdict()
        mock_doc.reference.path = doc_path

    def _mock_docs(
        self, documents: list[models.FireStoreDocument], doc_paths: list[str]
    ):
        mock_references = []
        for m, doc_path in zip(documents, doc_paths):
            mock_ref = mock.MagicMock()
            mock_doc = mock_ref.get()
            mock_doc.exists = True
            mock_doc.to_dict.return_value = m.asdict()
            mock_doc.reference.path = doc_path
            mock_references.append(mock_ref)
        self.mock_client.document.side_effect = mock_references

    @mock.patch("search.client.firestore.client")
    def test_index_meeting(self, mock_client_func: mock.Mock):
        mock_client_func.return_value = self.mock_client
        meet_no = uuid.uuid4().hex
        m = models.Meeting(meeting_no=meet_no, ai_summary=meet_no)
        self._mock_doc(m, f"meetings/{meet_no}")

        se = search_client.DocumentSearchEngine.create("xyz")
        se.index(f"meetings/{meet_no}", search_client.DocType.MEETING)
        assert se.query(m.meeting_no).hit_count > 0

    @mock.patch("search.client.firestore.client")
    def test_index_proceeding(self, mock_client_func: mock.Mock):
        mock_client_func.return_value = self.mock_client
        proc_no = uuid.uuid4().hex
        m = models.Proceeding(name=proc_no, status="finish", sponsors=["sponsor"])
        self._mock_doc(m, f"proceedings/{proc_no}")

        se = search_client.DocumentSearchEngine.create("xyz")
        se.index(f"proceedings/{proc_no}", search_client.DocType.PROCEEDING)

        assert se.query(proc_no).hit_count > 0
        assert se.query("sponsor").hit_count > 0
        assert se.query("finish").hit_count > 0

    @mock.patch("search.client.firestore.client")
    def test_index_meeting_file(self, mock_client_func: mock.Mock):
        mock_client_func.return_value = self.mock_client
        meet_no = uuid.uuid4().hex
        file_no = uuid.uuid4().hex
        meet_path = f"{models.MEETING_COLLECT}/{meet_no}"
        file_path = f"{meet_path}/{models.FILE_COLLECT}/{file_no}"
        file = models.MeetingFile(ai_summary=file_no)
        today = dt.datetime.now()
        yesterday = today - dt.timedelta(days=1)
        tomorrow = today + dt.timedelta(days=1)
        meet = models.Meeting(meeting_date_start=today)
        self._mock_docs([file, meet], [file_path, meet_path])

        se = search_client.DocumentSearchEngine.create("xyz")
        se.index(file_path, search_client.DocType.MEETING_FILE)

        assert (
            se.query(
                file_no, filter_by=f"created_date:>{int(yesterday.timestamp())}"
            ).hit_count
            > 0
        )
        assert (
            se.query(
                file_no, filter_by=f"created_date:>{int(tomorrow.timestamp())}"
            ).hit_count
            == 0
        )

    @mock.patch("search.client.firestore.client")
    def test_index_attachment(self, mock_client_func: mock.Mock):
        mock_client_func.return_value = self.mock_client
        proc_no = uuid.uuid4().hex
        attach_no = uuid.uuid4().hex
        proc_path = f"{models.PROCEEDING_COLLECT}/{proc_no}"
        attach_path = f"{proc_path}/{models.ATTACH_COLLECT}/{attach_no}"
        today = dt.datetime.now()
        yesterday = today - dt.timedelta(days=1)
        attach = models.Attachment(ai_summary=attach_no)
        proc = models.Proceeding(created_date=today)
        self._mock_docs(
            [attach, proc],
            [attach_path, proc_path],
        )

        se = search_client.DocumentSearchEngine.create("xyz")
        se.index(attach_path, search_client.DocType.ATTACHMENT)

        assert (
            se.query(
                attach_no, filter_by=f"created_date:>{int(yesterday.timestamp())}"
            ).hit_count
            > 0
        )

    def test_shadow_index_with_segments(self):
        db = firestore.client()
        uid = uuid.uuid4().hex
        doc_path = (
            f"{models.MEETING_COLLECT}/{uid}/{models.IVOD_COLLECT}/{uid}/"
            f"{models.SPEECH_COLLECT}/{uid}"
        )
        db.document(doc_path).set(
            models.Video(
                transcript="transcript",
            ).asdict()
        )
        segments = [
            models.SpeechSegment(start="00:01", end="00:02", text="hello"),
            models.SpeechSegment(start="00:10", end="00:12", text="greeting"),
        ]
        segment_collect = db.document(doc_path).collection(
            models.SPEECH_SEGMENT_COLLECT
        )
        for i, seg in enumerate(segments):
            segment_collect.document(str(i)).set(seg.asdict())

        se = search_client.DocumentSearchEngine.create("xyz")
        se.index(doc_path, search_client.DocType.VIDEO)

        hits_1: dict[str, Any] = se.typesense_client.collections[  # type: ignore
            "documents"
        ].documents.search(
            {
                "q": "hello",
                "query_by": "*",
            }
        )
        assert hits_1.get("found", 0) == 0
        hits_2: dict[str, Any] = se.typesense_client.collections[  # type: ignore
            "documents_v2"
        ].documents.search(
            {
                "q": "hello",
                "query_by": "*",
            }
        )
        assert hits_2.get("found", 0) == 1
        assert len(hits_2.get("hits", [])) == 1
        assert (
            hits_2.get("hits")[0].get("document", {}).get("path", None) == doc_path
        ), hits_2
        assert hits_2.get("hits")[0].get("document", {}).get("segments", {}), hits_2
        assert (
            hits_2.get("hits")[0].get("document", {}).get("transcript", None) is None
        ), (hits_2.get("hits")[0].get("document", {}).get("transcript", None))
        # Test if we stop indexing the transcript
        hits_transcript: dict[str, Any] = se.typesense_client.collections[  # type: ignore
            "documents_v2"
        ].documents.search(
            {
                "q": "transcript",
                "query_by": "*",
            }
        )
        assert hits_transcript.get("found", 0) == 0

    def test_shadow_index_without_segments(self):
        db = firestore.client()
        uid = uuid.uuid4().hex
        doc_path = (
            f"{models.MEETING_COLLECT}/{uid}/{models.IVOD_COLLECT}/{uid}/"
            f"{models.SPEECH_COLLECT}/{uid}"
        )
        db.document(doc_path).set(models.Video(transcript="hello").asdict())

        se = search_client.DocumentSearchEngine.create("xyz")
        se.index(doc_path, search_client.DocType.VIDEO)

        hits: dict[str, Any] = se.typesense_client.collections[  # type: ignore
            "documents"
        ].documents.search(
            {
                "q": "hello",
                "query_by": "*",
            }
        )
        assert hits.get("found", 0) == 1
