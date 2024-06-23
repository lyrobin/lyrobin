"""Test models."""

# pylint: disable=missing-function-docstring,missing-class-docstring
import unittest
import dataclasses
import datetime as dt
from legislature import models
import pytz

from google.cloud.firestore_v1.vector import Vector

_TZ = pytz.timezone("Asia/Taipei")


class TestModels(unittest.TestCase):

    _TEST_MEETING = {
        "term": "11",
        "sessionPeriod": "1 ",
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
        "attendLegislator": "XXX",
        "selectTerm": "all",
    }

    @dataclasses.dataclass
    class TestDocument(models.FireStoreDocument):
        name: str = ""
        empty: str = ""

    def test_firebase_document_from_dict(self):
        doc = self.TestDocument.from_dict({"name": "test", "age": 100})

        self.assertEqual(doc.name, "test")

    def test_firebase_document_to_dict(self):
        doc = self.TestDocument(name="test")
        self.assertEqual(
            doc.asdict(),
            {
                "name": "test",
                "ai_summarized": False,
                "ai_summarized_at": dt.datetime(1, 1, 1, 0, 0, tzinfo=dt.timezone.utc),
                "embedding_updated_at": dt.datetime(
                    1, 1, 1, 0, 0, tzinfo=dt.timezone.utc
                ),
                "last_update_time": dt.datetime(1, 1, 1, 0, 0, tzinfo=dt.timezone.utc),
            },
        )

    def test_meeting_convert_type(self):
        m: models.Meeting = models.Meeting.from_dict(self._TEST_MEETING)

        self.assertEqual(m.term, 11)
        self.assertEqual(
            m.meeting_date_start,
            dt.datetime(2024, 2, 1, 8, 0, tzinfo=_TZ),
        )
        self.assertEqual(
            m.meeting_date_end,
            dt.datetime(2024, 2, 1, 17, 0, tzinfo=_TZ),
        )

    def test_meeting_field_name_style(self):
        m: models.Meeting = models.Meeting.from_dict(self._TEST_MEETING)

        self.assertEqual(m.session_period, 1)

    def test_meeting_get_url(self):
        m: models.Meeting = models.Meeting.from_dict(self._TEST_MEETING)

        self.assertEqual(
            m.get_url(),
            "https://ppg.ly.gov.tw/ppg/sittings/2024013195/details?meetingDate=113/02/01",
        )


if __name__ == "__main__":
    unittest.main()
