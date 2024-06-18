# pylint: disable=attribute-defined-outside-init,missing-function-docstring,missing-module-docstring,protected-access

import dataclasses
import datetime as dt
import pathlib
import unittest
from urllib import parse

import pytest
import pytz
from legislature import readers
from utils import testings

# https://ppg.ly.gov.tw/ppg/bills/202110028120000/details
COMMITTEE_PROCEEDING_URL = "legislature_proceeding_2024042201.html"
# https://ppg.ly.gov.tw/ppg/sittings/2024042201/details
ALL_MEETING_PRCOEDING_URL = "legislature_proceeding_2024041742.html"
_TZ = pytz.timezone("Asia/Taipei")


def _test_file(name: str) -> pathlib.Path:
    return pathlib.Path(__file__).parent / "testdata" / name


# More test data:
# 1. https://ppg.ly.gov.tw/ppg/sittings/2024051758/details?meetingDate=113/05/17&meetingTime=12:00&departmentCode=null
# 2. https://ppg.ly.gov.tw/ppg/sittings/2024052281/details?meetingDate=113/05/28&meetingTime=&departmentCode=null -> multiple video
# 3. https://ppg.ly.gov.tw/ppg/sittings/2024052941/details?meetingDate=113/05/31&meetingTime=&departmentCode=null -> multiple video
class TestLegislativeMeetingReader(unittest.TestCase):
    """Test the LegislativeMeetingReader class."""

    def setUp(self) -> None:
        super().setUp()
        self._url = "https://ppg.ly.gov.tw/ppg/sittings/2024042201/details"
        self._qs = {
            "meetingDate": "113/04/25",
        }

    @testings.skip_when_no_network
    def test_open(self):
        r = readers.LegislativeMeetingReader.open(self._url, self._qs)

        self.assertIsNotNone(r)
        self.assertEqual(r._meeting_no, "2024042201")

    def test_get_related_proceedings(self):
        html = _test_file(COMMITTEE_PROCEEDING_URL).read_text()
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
        html = _test_file(COMMITTEE_PROCEEDING_URL).read_text()
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
        html = _test_file(COMMITTEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        attachments = r.get_files()
        urls = [a.url for a in attachments]
        names = [a.name for a in attachments]

        self.assertEqual(len(attachments), 2)
        self.assertSetEqual(
            set(urls),
            {
                "https://ppg.ly.gov.tw/ppg/SittingCommitteesInfo/download/communique1/final/pdf/113/34/LCIDC01_1133401_00001.pdf",
                "https://ppg.ly.gov.tw/ppg/download/communique1/work/113/34/LCIDC01_1133401_00002.doc",
            },
        )
        self.assertSetEqual(set(names), {"公報紀錄", "公報紀錄DOC"})

    @testings.skip_when_no_network
    def test_get_attachments_with_network(self):
        r = readers.LegislativeMeetingReader.open(self._url, self._qs)

        attachments = r.get_files(allow_download=True)

        self.assertEqual(len(attachments), 4)

    @testings.skip_when_no_network
    def test_get_attachments_with_zip(self):
        r = readers.LegislativeMeetingReader.open(
            "https://ppg.ly.gov.tw/ppg/sittings/2024040359/details",
            {"meetingDate": "113/04/09"},
        )

        attachments = r.get_files()

        self.assertEqual(len(attachments), 4)
        self.assertIn(
            "https://ppg.ly.gov.tw/ppg/sittings/download-publication?meetingNo=2024040359",
            [a.url for a in attachments],
        )

    def test_get_meeting_name(self):
        html = _test_file(COMMITTEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        name = r.get_meeting_name()

        self.assertEqual(name, "立法院第11屆第1會期司法及法制委員會第17次全體委員會議")

    def test_get_meeting_content(self):
        html = _test_file(COMMITTEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        content = r.get_meeting_content()
        self.assertIn(
            "（一）民進黨黨團擬具「立法院組織法部分條文修正草案」案。",
            content.splitlines(),
        )

    def test_get_meeting_room(self):
        html = _test_file(COMMITTEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        room = r.get_meeting_room()

        self.assertEqual(room, "紅樓302會議室")

    def test_get_meeting_date(self):
        html = _test_file(COMMITTEE_PROCEEDING_URL).read_text()
        r = readers.LegislativeMeetingReader(html)

        date_desc = r.get_meeting_date_desc()

        self.assertEqual(date_desc, "113/04/25 09:00-17:30")


# Proceedings
# 1. https://ppg.ly.gov.tw/ppg/bills/202110027130000/details -> more links to proceedings
#    (the proceeding page may update..., need to fetch it regularly?)
# 2. https://ppg.ly.gov.tw/ppg/bills/202110028120000/details -> single doc
# 3. https://ppg.ly.gov.tw/ppg/bills/202110002450000/details -> 協商
# 4. https://ppg.ly.gov.tw/ppg/bills/603110035420000/details -> multiple docs
# link keyword: https://ppg.ly.gov.tw/ppg/download
@dataclasses.dataclass
class ProceedingReaderTestCase:
    bill: str
    related_bills: list[readers.ProceedingEntry] | None = None
    status: str | None = None
    attachments: list[readers.AttachmentEntry] | None = None
    proposers: list[str] | None = None
    sponsers: list[str] | None = None
    progress: list[readers.StepEntry] | None = None

    def get_url(self) -> str:
        return f"https://ppg.ly.gov.tw/ppg/bills/{self.bill}/details"


read_proeedings_testcases = [
    # https://ppg.ly.gov.tw/ppg/bills/202110027130000/details
    ProceedingReaderTestCase(
        bill="202110027130000",
        status="三讀",
        related_bills=[
            readers.ProceedingEntry(
                name="咨請公布",
                bill_no="1130702162",
                url="https://ppg.ly.gov.tw/ppg/bills/latest-pass-third-readings/1130702162/process",
            ),
            readers.ProceedingEntry(
                name="本院司法及法制委員會報告併案審查台灣民眾黨黨團、委員楊瓊瓔等20人、委員傅崐萁等52人、委員傅崐萁等52人分別擬具「立法院職權行使法部分條文修正草案」、委員翁曉玲等16人擬具「立法院職權行使法第十五條、第二十九條及第四十四條條文修正草案」、委員傅崐萁等52人、委員翁曉玲等16人分別擬具「立法院職權行使法第十五條之一、第十五條之二及第十五條之四條文修正草案」、委員吳宗憲等16人擬具「立法院職權行使法部分條文修正草案」、委員吳宗憲等17人擬具「立法院職權行使法第十七條條文修正草案」、委員吳宗憲等17人擬具「立法院職權行使法部分條文修正草案」、委員吳宗憲等16人擬具「立法院職權行使法第十五條之一、第十五條之二及第十五條之四條文修正草案」、委員賴瑞隆等17人擬具「立法院職權行使法第十五條之二條文修正草案」、委員賴士葆等20人擬具「立法院職權行使法增訂部分條文草案」、委員吳宗憲等18人擬具「立法院職權行使法第二十五條及第二十六條條文修正草案」及委員翁曉玲等18人擬具「立法院職權行使法第二十五條條文修正草案」案。",
                bill_no="603110035420000",
                url="https://ppg.ly.gov.tw/ppg/bills/603110035420000/details",
            ),
            readers.ProceedingEntry(
                name="本院委員羅智強等31人「立法院職權行使法第二十二條、第二十三條及第二十八條條文修正草案」，請審議案。",
                bill_no="202110033840000",
                url="https://ppg.ly.gov.tw/ppg/bills/202110033840000/details",
            ),
            readers.ProceedingEntry(
                name="本院委員羅智強等16人「立法院職權行使法部分條文修正草案」，請審議案。",
                bill_no="202110033850000",
                url="https://ppg.ly.gov.tw/ppg/bills/202110033850000/details",
            ),
            readers.ProceedingEntry(
                name="本院委員呂玉玲等16人「立法院職權行使法增訂第二十八條之三及第二十八條之四條文草案」，請審議案。",
                bill_no="202110027140000",
                url="https://ppg.ly.gov.tw/ppg/bills/202110027140000/details",
            ),
            readers.ProceedingEntry(
                name="本院委員鄭天財Sra Kacaw等19人「立法院職權行使法部分條文修正草案」，請審議案。",
                bill_no="202110027460000",
                url="https://ppg.ly.gov.tw/ppg/bills/202110027460000/details",
            ),
            readers.ProceedingEntry(
                name="本院委員翁曉玲等17人「立法院職權行使法部分條文修正草案」，請審議案。",
                bill_no="202110027820000",
                url="https://ppg.ly.gov.tw/ppg/bills/202110027820000/details",
            ),
            readers.ProceedingEntry(
                name="本院委員羅智強等22人「立法院職權行使法第二十五條條文修正草案」，請審議案。",
                bill_no="202110029120000",
                url="https://ppg.ly.gov.tw/ppg/bills/202110029120000/details",
            ),
        ],
        attachments=[
            readers.AttachmentEntry(
                name="關係文書PDF",
                url="https://ppg.ly.gov.tw/ppg/download/agenda1/02/pdf/11/01/14/LCEWA01_110114_00278.pdf",
            ),
            readers.AttachmentEntry(
                name="關係文書DOC",
                url="https://ppg.ly.gov.tw/ppg/download/agenda1/02/word/11/01/14/LCEWA01_110114_00278.doc",
            ),
        ],
        proposers=["呂玉玲"],
        sponsers=[
            "邱鎮軍",
            "盧縣一",
            "涂權吉",
            "許宇甄",
            "羅廷瑋",
            "鄭天財Sra Kacaw",
            "葉元之",
            "林倩綺",
            "洪孟楷",
            "柯志恩",
            "牛煦庭",
            "馬文君",
            "陳菁徽",
            "蘇清泉",
            "廖偉翔",
            "王育敏",
        ],
        progress=[
            readers.StepEntry(
                name="排入院會 (交司法及法制委員會)",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=11-01-08;113/04/09;院會",
                title="院會 11-01-08",
            ),
            readers.StepEntry(
                name="交付審查",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=11-01-08;113/04/09;院會",
                title="院會 11-01-08",
            ),
            readers.StepEntry(
                name="委員會審查",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=2024041640;113/04/18;司法及法制委員會",
                title="司法及法制委員會",
            ),
            readers.StepEntry(
                name="委員會審查",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=2024042201;113/04/25;司法及法制委員會",
                title="司法及法制委員會",
            ),
            readers.StepEntry(
                name="委員會抽出逕付二讀(交付協商)",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=11-01-12;113/05/03;院會",
                title="院會 11-01-12",
            ),
            readers.StepEntry(
                name="排入院會(討論事項)",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=11-01-14;113/05/17;院會",
                title="院會 11-01-14",
            ),
            readers.StepEntry(
                name="排入院會(討論事項)",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=11-01-15;113/05/24;院會",
                title="院會 11-01-15",
            ),
            readers.StepEntry(
                name="三讀",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=11-01-15;113/05/24;院會",
                title="院會 11-01-15",
            ),
        ],
    ),
    # https://ppg.ly.gov.tw/ppg/bills/202110028120000/details
    ProceedingReaderTestCase(
        bill="202110028120000",
        related_bills=[
            readers.ProceedingEntry(
                url="https://ppg.ly.gov.tw/ppg/bills/203110041470000/details",
                name="司法及法制委員會報告併案審查民進黨黨團擬具「立法院組織法部分條文修正草案」、委員高金素梅等23人擬具「立法院組織法第三十二條條文修正草案」、委員賴瑞隆等16人擬具「立法院組織法第三條、第五條及第三十二條條文修正草案」及委員高金素梅等17人擬具「立法院組織法第三十三條條文修正草案」案。",
            ),
            readers.ProceedingEntry(
                url="https://ppg.ly.gov.tw/ppg/bills/202110022460000/details",
                name="本院委員高金素梅等23人「立法院組織法第三十二條條文修正草案」，請審議案。",
            ),
            readers.ProceedingEntry(
                url="https://ppg.ly.gov.tw/ppg/bills/202110027080000/details",
                name="本院委員賴瑞隆等16人「立法院組織法第三條、第五條及第三十二條條文修正草案」，請審議案。",
            ),
            readers.ProceedingEntry(
                url="https://ppg.ly.gov.tw/ppg/bills/202110013220000/details",
                name="本院委員高金素梅等17人「立法院組織法第三十三條條文修正草案」，請審議案。",
            ),
        ],
        status="審查完畢",
        attachments=[
            readers.AttachmentEntry(
                name="關係文書PDF",
                url="https://ppg.ly.gov.tw/ppg/download/agenda1/02/pdf/11/01/08/LCEWA01_110108_00111.pdf",
            ),
            readers.AttachmentEntry(
                name="關係文書DOC",
                url="https://ppg.ly.gov.tw/ppg/download/agenda1/02/word/11/01/08/LCEWA01_110108_00111.doc",
            ),
        ],
        proposers=[
            "柯建銘",
            "吳思瑤",
            "莊瑞雄",
        ],
        sponsers=[],
        progress=[
            readers.StepEntry(
                name="排入院會 (交司法及法制委員會)",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=11-01-08;113/04/09;院會",
                title="院會 11-01-08",
            ),
            readers.StepEntry(
                name="交付審查",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=11-01-08;113/04/09;院會",
                title="院會 11-01-08",
            ),
            readers.StepEntry(
                name="委員會審查",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=2024041973;113/04/22;司法及法制委員會",
                title="司法及法制委員會",
            ),
            readers.StepEntry(
                name="委員會審查",
                url="https://ppg.ly.gov.tw/ppg/sittings/meetingLink/?id=2024042201;113/04/25;司法及法制委員會",
                title="司法及法制委員會",
            ),
            readers.StepEntry(name="委員會發文", title="司法及法制委員會", url=""),
        ],
    ),
]


@pytest.mark.parametrize(
    "t",
    read_proeedings_testcases,
    ids=[t.bill for t in read_proeedings_testcases],
)
@testings.skip_when_no_network
def test_read_proceeding(t: ProceedingReaderTestCase):

    r = readers.ProceedingReader.open(t.get_url())

    if t.related_bills is not None:
        assert set(r.get_related_bills()) == set(t.related_bills)

    if t.status is not None:
        assert r.get_status() == t.status

    if t.attachments is not None:
        assert set(r.get_attachments()) == set(t.attachments)

    if t.proposers is not None:
        assert set(r.get_proposers()) == set(t.proposers)

    if t.sponsers is not None:
        assert set(r.get_sponsors()) == set(t.sponsers)

    if t.progress is not None:
        assert set(r.get_progress()) == set(t.progress)


@dataclasses.dataclass
class IvodReaderTestCase:
    meet: str = ""
    videos: list[readers.VideoEntry] | None = None
    speeches: list[readers.VideoEntry] | None = None

    def get_url(self):
        qs = parse.urlencode({"Meet": self.meet})
        return f"https://ivod.ly.gov.tw/Demand/Meetvod?{qs}"


read_ivod_testcases: list[IvodReaderTestCase] = [
    # https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00132704226422162141
    IvodReaderTestCase(
        meet="00132704226422162141",
        videos=[
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Full/300K/15925",
                member="",
            ),
        ],
        speeches=[
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152673",
                member="李坤城",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152672",
                member="蘇巧慧",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152671",
                member="蔡易餘",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152670",
                member="吳思瑤",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152669",
                member="沈發惠",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152668",
                member="吳思瑤",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152667",
                member="范雲",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152666",
                member="吳思瑤",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152665",
                member="吳思瑤",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152664",
                member="吳思瑤",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Clip/300K/152663",
                member="鍾佳濱",
            ),
        ],
    ),
    # https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00692054771069304605
    IvodReaderTestCase(
        meet="00692054771069304605",
        videos=[
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Full/300K/15928",
                member="",
            ),
            readers.VideoEntry(
                url="https://ivod.ly.gov.tw/Play/Full/300K/15927",
                member="",
            ),
        ],
        speeches=[],
    ),
]


@pytest.mark.parametrize(
    "t",
    read_ivod_testcases,
    ids=[t.meet for t in read_ivod_testcases],
)
@testings.skip_when_no_network
def test_read_ivod(t: IvodReaderTestCase):
    r = readers.IvodReader.open(t.get_url())

    if t.videos is not None:
        assert set(r.get_videos()) == set(t.videos)

    if t.speeches is not None:
        assert set(r.get_member_speeches()) == set(t.speeches)


# Videos
# 1. https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00692054771069304605 -> 黨團協商
# 2. https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00046578846529964859 -> commitee
# 3. 院會, 複雜 (會議: https://ppg.ly.gov.tw/ppg/sittings/2024051509/details?meetingDate=113/05/17&meetingTime=&departmentCode=null)
#    (1) https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00132704226422162141
#    (2) https://ivod.ly.gov.tw/Demand/Meetvod?Meet=00299965961770109694
#    [跨兩天]


class TestVideoReader(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        html = _test_file("ivod.ly.gov.tw_Play_Clip_300K_152663.html").read_text()
        self.r = readers.VideoReader(html)

    def test_meta(self):
        assert (
            self.r.playlist_url
            == "https://ivod-lyvod.cdn.hinet.net/vod_1/_definst_/mp4:300KClips/61a8f637e1ac8289c4688db388786c88bc07d65983179d7b050a560fc7837330e3de8b0d8230918a5ea18f28b6918d91.mp4/playlist.m3u8"
        )
        assert self.r.meta.duration == dt.timedelta(minutes=4, seconds=4)
        assert self.r.meta.start_time == dt.datetime(
            year=2024, month=5, day=17, hour=18, minute=27, second=12, tzinfo=_TZ
        )
        assert self.r.meta.end_time == dt.datetime(
            year=2024, month=5, day=17, hour=18, minute=31, second=16, tzinfo=_TZ
        )

    @unittest.skip("for manual tests")
    @testings.skip_when_no_network
    def test_m3u8(self):
        r = readers.VideoReader.open("https://ivod.ly.gov.tw/Play/Clip/300K/152663")
        assert r._target_duration == 11
        assert r._clip_chunks == 164
        assert r.clips_count == 1
        r.set_clip_size(dt.timedelta(seconds=30))
        assert r.clips_count == 9

    @testings.skip_when_no_network
    def test_video_without_mov_time(self):
        r = readers.VideoReader.open("https://ivod.ly.gov.tw/Play/Full/300K/15664")

        assert r.meta.start_time == dt.datetime(
            year=2024, month=2, day=1, hour=7, minute=45, second=2, tzinfo=_TZ
        )
        assert r.meta.duration == dt.timedelta(seconds=34318)


class TestDocumentReader(unittest.TestCase):

    @testings.skip_when_no_network
    def test_parse_pdf(self):
        r = readers.DocumentReader.open(
            "https://ppg.ly.gov.tw/ppg/download/agenda1/02/pdf/11/01/03/LCEWA01_110103_00056.pdf"
        )

        assert "立法院議案關係文書" in r.content

    @testings.skip_when_no_credential
    @testings.skip_when_no_network
    def test_parse_doc(self):

        r = readers.DocumentReader.open(
            "https://ppg.ly.gov.tw/ppg/download/agenda1/02/word/11/01/03/LCEWA01_110103_00056.doc"
        )

        assert "立法院議案關係文書" in r.content


if __name__ == "__main__":
    unittest.main()
