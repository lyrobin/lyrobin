"""Test models."""

# pylint: disable=missing-function-docstring,missing-class-docstring
import unittest
import dataclasses
import datetime as dt
from legislature import models


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
        name: str

    def test_firebase_document_from_dict(self):
        doc = self.TestDocument.from_dict({"name": "test", "age": 100})

        self.assertEqual(doc.name, "test")

    def test_meeting_convert_type(self):
        m: models.Meeting = models.Meeting.from_dict(self._TEST_MEETING)

        self.assertEqual(m.term, 11)
        self.assertEqual(m.meeting_date_start, dt.datetime(2024, 2, 1, 8, 0))
        self.assertEqual(m.meeting_date_end, dt.datetime(2024, 2, 1, 17, 0))

    def test_meeting_field_name_style(self):
        m: models.Meeting = models.Meeting.from_dict(self._TEST_MEETING)

        self.assertEqual(m.session_period, 1)


if __name__ == "__main__":
    unittest.main()
