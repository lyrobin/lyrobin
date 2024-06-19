import unittest
import uuid
from unittest import mock
import datetime as dt

from legislature import models
from search import client as search_client


@mock.patch("search.client.firestore.client")
class ClientTest(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.mock_client = mock.MagicMock()

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

    def test_index_meeting(self, mock_client_func: mock.Mock):
        mock_client_func.return_value = self.mock_client
        meet_no = uuid.uuid4().hex
        m = models.Meeting(meeting_no=meet_no, ai_summary=meet_no)
        self._mock_doc(m, f"meetings/{meet_no}")

        se = search_client.DocumentSearchEngine.create("xyz")
        se.index(f"meetings/{meet_no}", search_client.DocType.MEETING)
        assert se.query(m.meeting_no).hit_count > 0

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
