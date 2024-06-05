"""
Test for legislative_parser.py
"""

# pylint: disable=missing-function-docstring
import unittest

import utils
from utils import testings
from firebase_admin import firestore
from legislature import models
import requests


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
    def test_fetch_meeting_from_web(self):
        m: models.Meeting = models.Meeting.from_dict(
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

        url = utils.get_function_url("fetch_meeting_from_web")
        print(url)
        res = requests.post(
            url,
            json={"data": {"meetNo": m.meeting_no, "url": m.get_url()}},
            headers={"content-type": "application/json"},
            timeout=60,
        )
        videos = list(
            self.db.collection("meetings")
            .document(m.meeting_no)
            .collection("videos")
            .stream()
        )

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(len(videos), 1)


if __name__ == "__main__":
    unittest.main()
