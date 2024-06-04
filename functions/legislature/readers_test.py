# pylint: disable=attribute-defined-outside-init,missing-function-docstring,missing-module-docstring,protected-access

import os
import pathlib
import unittest
from legislature import readers

# https://ppg.ly.gov.tw/ppg/bills/202110028120000/details
COMMITEE_PROCEEDING_URL = "legislature_proceeding_2024042201.html"
# https://ppg.ly.gov.tw/ppg/sittings/2024042201/details
ALL_MEETING_PRCOEDING_URL = "legislature_proceeding_2024041742.html"

HAS_NETWORK_ACCESS = os.environ.get("NETWORK_TEST", "False").lower() in (
    "true",
    "1",
)


def _test_file(name: str) -> pathlib.Path:
    return pathlib.Path(__file__).parent / "testdata" / name


class TestLegislativeMeetingReader(unittest.TestCase):
    """Test the LegislativeMeetingReader class."""

    def setUp(self) -> None:
        super().setUp()
        self._url = "https://ppg.ly.gov.tw/ppg/sittings/2024042201/details"
        self._qs = {
            "meetingDate": "113/04/25",
        }

    @unittest.skipUnless(HAS_NETWORK_ACCESS, "Network test disabled")
    def test_open(self):
        r = readers.LegislativeMeetingReader.open(self._url, self._qs)

        self.assertIsNotNone(r)
        self.assertEqual(r._meeting_no, "2024042201")

    def test_get_related_proceedings(self):
        html = _test_file(COMMITEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        procs = r.get_related_proceedings()
        urls = [p.url for p in procs]
        bill_numbers = [p.bill_no for p in procs]
        names = [p.name for p in procs]

        self.assertEqual(len(procs), 15)
        self.assertIn("https://ppg.ly.gov.tw/ppg/bills/202110028120000/details", urls)
        self.assertIn("202110028120000", bill_numbers)
        self.assertIn(
            "本院委員高金素梅等23人擬具「立法院組織法第三十二條條文修正草案」，請審議案。",
            names,
        )

    def test_get_videos_one_video(self):
        html = _test_file(COMMITEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        videos = r.get_videos()
        urls = [v.url for v in videos]
        names = [v.name for v in videos]

        self.assertEqual(len(videos), 1)
        self.assertSetEqual(
            set(urls),
            {"https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00756102736747508086"},
        )
        self.assertSetEqual(set(names), {"會議影片"})

    def test_get_videos_two_videos(self):
        html = _test_file(ALL_MEETING_PRCOEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        videos = r.get_videos()
        urls = [v.url for v in videos]
        names = [v.name for v in videos]

        self.assertEqual(len(videos), 2)
        self.assertSetEqual(
            set(urls),
            {
                "https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00048495654265779043",
                "https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00487362154253375676",
            },
        )
        self.assertSetEqual(set(names), {"會議影片1", "會議影片2"})

    def test_get_attachments(self):
        html = _test_file(COMMITEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        attachs = r.get_files()
        urls = [a.url for a in attachs]
        names = [a.name for a in attachs]

        self.assertEqual(len(attachs), 2)
        self.assertSetEqual(
            set(urls),
            {
                "https://ppg.ly.gov.tw/ppg/SittingCommitteesInfo/download/communique1/final/pdf/113/34/LCIDC01_1133401_00001.pdf",
                "https://ppg.ly.gov.tw/ppg/download/communique1/work/113/34/LCIDC01_1133401_00002.doc",
            },
        )
        self.assertSetEqual(set(names), {"公報紀錄", "公報紀錄DOC"})

    @unittest.skipUnless(HAS_NETWORK_ACCESS, "Network test disabled")
    def test_get_attachments_with_network(self):
        r = readers.LegislativeMeetingReader.open(self._url, self._qs)

        attachs = r.get_files(allow_download=True)

        self.assertEqual(len(attachs), 4)

    @unittest.skipUnless(HAS_NETWORK_ACCESS, "Network test disabled")
    def test_get_attachments_with_zip(self):
        r = readers.LegislativeMeetingReader.open(
            "https://ppg.ly.gov.tw/ppg/sittings/2024040359/details",
            {"meetingDate": "113/04/09"},
        )

        attachs = r.get_files()

        self.assertEqual(len(attachs), 4)
        self.assertIn(
            "https://ppg.ly.gov.tw/ppg/sittings/download-publication?meetingNo=2024040359",
            [a.url for a in attachs],
        )

    def test_get_meeting_name(self):
        html = _test_file(COMMITEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        name = r.get_meeting_name()

        self.assertEqual(name, "立法院第11屆第1會期司法及法制委員會第17次全體委員會議")

    def test_get_meeting_content(self):
        html = _test_file(COMMITEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        content = r.get_meeting_content()
        self.assertIn(
            "（一）民進黨黨團擬具「立法院組織法部分條文修正草案」案。",
            content.splitlines(),
        )


if __name__ == "__main__":
    unittest.main()
