"""
A module to read a legislative pages.
"""

import dataclasses
import datetime as dt
import io
import json
import math
import pathlib
import re
import tempfile
from urllib import parse

import bs4
import ffmpeg
import google.auth.transport.requests
import google.oauth2.id_token
import m3u8
import m3u8.model
import params
import pytz
import requests
import textract

_REQUEST_HEADEER = {
    "User-Agent": " ".join(
        [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "AppleWebKit/537.36 (KHTML, like Gecko)",
            "Chrome/91.0.4472.124",
            "Safari/537.36",
        ]
    ),
}

_GET_PROCEEDINGS_API = "https://ppg.ly.gov.tw/ppg/api/v1/getProceedingsList"

_TZ = pytz.timezone("Asia/Taipei")


@dataclasses.dataclass(unsafe_hash=True)
class ProceedingEntry:
    """A class to represent a legislative meeting proceedings."""

    name: str
    url: str
    bill_no: str = ""

    def __post_init__(self):
        if not self.bill_no and self.url:
            parsed_url = parse.urlparse(self.url)
            self.bill_no = parsed_url.path.strip("/").split("/")[-2]


@dataclasses.dataclass(unsafe_hash=True)
class AttachmentEntry:
    """A class to represent an attached file."""

    name: str
    url: str


@dataclasses.dataclass(unsafe_hash=True)
class StepEntry:
    """Proceedings review steps"""

    name: str = ""
    title: str = ""
    meeting_id: str = ""
    date: str = ""
    url: str = ""

    def __post_init__(self):
        parsed_url = parse.urlparse(self.url)
        _id = parse.parse_qs(parsed_url.query).get("id")
        if not _id:
            return
        _id = _id[0]
        self.meeting_id, self.date = _id.split(";")


@dataclasses.dataclass(unsafe_hash=True)
class VideoEntry:
    """A class to represent a video"""

    url: str = ""
    member: str | None = None


@dataclasses.dataclass(unsafe_hash=True)
class LegislativeMeetingReader:
    """A class to read a legislative meeting page."""

    # ppg/bills/202110028120000/details
    _BILL_REGEX = re.compile(r"/ppg/bills/(\d+)/details")

    def __init__(self, html: str, url: str = None):
        self._s = bs4.BeautifulSoup(html, "html.parser")
        if url is None:
            return
        parsed_url = parse.urlparse(url)
        self._meeting_no = parsed_url.path.strip("/").split("/")[-2]
        self._origin = f"{parsed_url.scheme}://{parsed_url.netloc}"

    @classmethod
    def open(
        cls, url: str, qs: dict[str, any] = None, timeout=60
    ) -> "LegislativeMeetingReader":
        """Open a legislative meeting page."""
        if qs is None:
            qs = parse.urlparse(url).params
        res = requests.get(url, params=qs, timeout=timeout, headers=_REQUEST_HEADEER)
        if res.status_code != 200:
            raise IOError(f"Failed to open {url}: {res.text}")
        return cls(res.text, url)

    def get_related_proceedings(self) -> list[ProceedingEntry]:
        """Get a list of proceedings."""
        bill_links: list[bs4.Tag] = self._s.find_all("a", href=self._BILL_REGEX)
        return [
            ProceedingEntry(
                name=a.string,
                url=a["href"],
                bill_no=self._get_bill_no(a["href"]),
            )
            for a in bill_links
        ]

    def get_videos(self) -> list[AttachmentEntry]:
        """Get a list of videos (IVODs)."""
        sec = self._get_main_section()
        return [
            AttachmentEntry(
                name=self._get_badge_name(a),
                url=a["href"],
            )
            for a in sec.find_all(self._is_link_to_video)
        ]

    def get_files(self, allow_download=False) -> list[AttachmentEntry]:
        """Get a list of files.

        Args:
            allow_download (bool, optional): Allow download of files. Defaults to False.
                The links to files may not be available on the static page.
                Allow to click the badge to download the file.
        """
        sec = self._get_main_section()
        attachments = []
        for a in sec.find_all(self._is_link_to_attachment):
            if "href" not in a.attrs:
                if allow_download:
                    attachments.extend(self._fetch_proceedings())
            elif not a["href"].startswith("http"):
                href = self._parse_zip_link(a["href"])
                if href is None:
                    continue
                attachments.append(
                    AttachmentEntry(
                        name=self._get_badge_name(a),
                        url=href,
                    )
                )
            else:
                attachments.append(
                    AttachmentEntry(
                        name=self._get_badge_name(a),
                        url=a["href"],
                    )
                )
        return attachments

    def get_meeting_name(self):
        """Get the name of the meeting"""
        sec = self._get_main_section()
        return sec.find("div", class_="row").find("span").string

    def get_meeting_content(self):
        """Get the content of the meeting"""
        sec = self._get_main_section()
        return "\n".join(sec.find("span", class_="card-title").strings)

    def get_meeting_room(self):
        """Get the room of the meeting"""
        sec = self._get_main_section()
        return "".join(sec.find("i", class_="fa-map-pin").parent.strings).strip()

    def get_meeting_date_desc(self):
        """Get the date and time of the meeting in y/m/d H:M-H:M format"""
        sec = self._get_main_section()
        date: bs4.Tag = (
            sec.find("div", class_="card-body")
            .find("div", class_="row")
            .find(self._is_date_span)
        )
        des = date.string
        y, des = des.split("年")
        m, des = des.split("月")
        d, des = des.split("日")
        t = des.split(")")[1].strip()
        return f"{y}/{m}/{d} {t}"

    def _fetch_proceedings(self, timeout=60) -> list[AttachmentEntry]:
        """Fetch proceedings with API."""
        res = requests.get(
            _GET_PROCEEDINGS_API,
            params={"meetingNo": self._meeting_no},
            headers=_REQUEST_HEADEER,
            timeout=timeout,
        )
        if res.status_code != 200:
            raise IOError(f"Failed to fetch proceedings: {res.text}")
        data: dict[str, str] = res.json()
        return [
            AttachmentEntry(name=name, url=url)
            for url, name in [v.split(";") for v in data.values()]
        ]

    def _get_badge_name(self, tag: bs4.Tag):
        return tag.find(lambda t: t.name == "span" and not t.has_attr("class")).string

    def _is_link_to_video(self, tag: bs4.Tag) -> bool:
        """Check if a tag is a link to a video."""
        if tag.name != "a":
            return False
        badge = tag.find("span", class_="BadgeIcon")
        if not badge:
            return False
        return badge.find("i", class_="fa-video") is not None

    def _is_link_to_attachment(self, tag: bs4.Tag) -> bool:
        """Check if a tag is a link to an attachment."""
        if tag.name != "a":
            return False
        return tag.find("i", class_="fa-download") is not None

    def _get_main_section(self) -> bs4.Tag:
        """Get the main section of the page."""
        outter = self._s.find("section", id="section-0")
        return outter.find("article")

    def _get_bill_no(self, url: str) -> str:
        """Get the bill number from a URL."""
        return self._BILL_REGEX.search(url).group(1)

    def _parse_zip_link(self, url: str) -> str | None:
        """Parse a zip link."""
        location_parts = url.split("location=")[-1]
        if not location_parts:
            return None
        return self._origin + location_parts.strip("'")

    def _is_date_span(self, tag: bs4.Tag) -> bool:
        """Check if a tag is a date span."""
        if tag.name != "span":
            return False
        if "card-title" in tag.attrs.get("class", []):
            return False
        if tag.string is None:
            return False
        keywords = ["年", "月", "日"]
        if not all(k in tag.string for k in keywords):
            return False
        return True


class ProceedingReader:
    """Read a proceedings"""

    def __init__(self, html: str, url: str):
        self._s = bs4.BeautifulSoup(html, "html.parser")
        prased_url = parse.urlparse(url)
        self._origin = f"{prased_url.scheme}://{prased_url.netloc}"

    @classmethod
    def open(cls, url: str) -> "ProceedingReader":
        """Open a proceedings"""
        res = requests.get(url, headers=_REQUEST_HEADEER, timeout=60)
        if res.status_code != 200:
            raise IOError(f"Failed to fetch proceedings: {res.text}")
        return cls(res.text, url)

    def _prepend_domain_name(self, url: str) -> str:
        if url.startswith("http"):
            return url
        return parse.urljoin(self._origin, url)

    def get_related_bills(self) -> list[ProceedingEntry]:
        """Get a list of related bills."""

        def _is_link_to_bill(tag: bs4.Tag) -> bool:
            if tag.name != "a" or "href" not in tag.attrs:
                return False
            return "/ppg/bills" in tag["href"]

        def _to_proceeding(tag: bs4.Tag) -> ProceedingEntry:
            if tag.name != "a":
                raise TypeError(f"Expected a tag, got {tag.name}")

            return ProceedingEntry(
                name=tag.string,
                url=self._prepend_domain_name(tag["href"]),
            )

        sec = self._s.find("article", id="section-0")
        links: list[bs4.Tag] = sec.find_all(_is_link_to_bill) if sec else []

        sec = self._s.find("article", id="section-2")
        if sec:
            links.extend(sec.find_all(_is_link_to_bill))

        return [_to_proceeding(tag) for tag in links]

    def _get_members(self, role: str) -> list[str]:
        sec = self._s.find("article", id="section-1")

        def _is_member_sec(tag: bs4.Tag) -> bool:
            if tag.name != "div":
                return False
            span = tag.find("span", recursive=False)
            if not span:
                return False
            return role in span.string

        psec = sec.find(_is_member_sec)
        if not psec:
            return []
        return [l.find("a").string for l in psec.find_all("li")]

    def get_proposers(self) -> list[str]:
        """Get a list of proposers."""
        return self._get_members("提案人")

    def get_sponsors(self) -> list[str]:
        """Get a list of sponsors"""
        return self._get_members("連署人")

    def get_status(self) -> str:
        """Get the status of the proceedings"""
        sec = self._s.find("article", id="section-0").find("div", class_="card-body")
        div = sec.find(lambda t: t.name == "div" and "class" not in t.attrs)
        return div.find("span").string.strip()

    def get_attachments(self) -> list[AttachmentEntry]:
        """Get a list of attachments"""
        sec = self._s.find("article", id="section-0").find("div", class_="card-body")
        links = sec.find_all(
            lambda t: t.name == "a" and "/ppg/download" in t.attrs.get("href", "")
        )
        return [
            AttachmentEntry(
                name="".join(s.strip() for s in l.strings),
                url=self._prepend_domain_name(l["href"]),
            )
            for l in links
        ]

    def get_progress(self) -> list[StepEntry]:
        """Get a list of progress"""

        def _to_step(tag: bs4.Tag) -> StepEntry:
            name = tag.find("span", class_="Detail-SkedGroup-Sp").string
            link = tag.find(
                lambda a: a.name == "a"
                and "/ppg/sittings/meetingLink" in a.attrs.get("href", "")
            )
            if link:
                return StepEntry(
                    name=name,
                    title=link.string,
                    url=self._prepend_domain_name(link["href"]),
                )
            try:
                title = tag.find("span", class_="card-title").find("span").string
            except AttributeError:
                title = ""
            return StepEntry(
                name=name,
                title=title,
            )

        sec = self._s.find("article", id="section-3")
        g = sec.find("div", class_="Detail-SkedGroup")
        details = g.find_all("dl", class_="Detail-Sked")
        return [_to_step(d) for d in details]


class IvodReader:
    """Read an ivod"""

    def __init__(self, html: str, url: str):
        self._s = bs4.BeautifulSoup(html, "html.parser")
        purl = parse.urlparse(url)
        self._origin = f"{purl.scheme}://{purl.netloc}"
        self._url = f"{purl.scheme}://{purl.netloc}/{purl.path}"
        qs = parse.parse_qs(purl.query.lower())
        self._meet = qs.get("meet", [""])[0]
        self._page = int(qs.get("page", [1])[0])

    @classmethod
    def open(cls, url: str):
        """Open an ivod"""
        res = requests.get(url, headers=_REQUEST_HEADEER, timeout=60)
        if res.status_code != 200:
            raise IOError(f"Failed to fetch ivod {url}")
        return cls(res.text, url)

    def get_videos(self) -> list[VideoEntry]:
        """Get a list of videos, exclude the member speeches."""
        sec = self._s.find("div", class_="committee-data-info")
        if not sec:
            return []
        videos = [self._to_video_entry(v) for v in sec.find_all("div", recursive=False)]
        return [v for v in videos if v is not None]

    def get_member_speeches(
        self, recursive: bool = True, max_page: int = 20
    ) -> list[VideoEntry]:
        """Get a list of member speeches.

        Args:
            recursive (bool, optional): Whether to read the speeches in all pages. Defaults to True.
            max_page (int, optional): The maximum number of pages to read. Defaults to 20.

        Returns:
            list[VideoEntry]: A list of member speeches (VideoEntry)
        """
        if not recursive:
            return self._get_member_speeches()
        videos = []
        ptr = self
        for _ in range(max_page):
            _vidoes = ptr.get_member_speeches(recursive=False)
            if not _vidoes:
                break
            videos.extend(_vidoes)
            ptr = ptr.next_page()
        return videos

    def _get_member_speeches(self) -> list[VideoEntry]:
        sec = self._s.find("div", class_="clip-list")
        if not sec:
            return []
        videos = [self._to_video_entry(v) for v in sec.find_all("li")]
        return [v for v in videos if v is not None]

    def next_page(self) -> "IvodReader":
        """Get the next page of the ivod."""
        qs = parse.urlencode(
            {
                "Meet": self._meet,
                "page": self._page + 1,
            }
        )
        return IvodReader.open(f"{self._url}?{qs}")

    def _to_video_entry(self, tag: bs4.Tag) -> VideoEntry:
        link_tag = tag.find(
            lambda t: t.name == "a"
            and t.attrs.get("href", "").startswith("/Play")
            and "窄頻" in t.attrs.get("title", "")
        )
        if not link_tag:
            return None
        link = link_tag["href"]
        text = tag.find("div", class_="clip-list-text")
        member_tag = (
            text.find(
                lambda t: t.name == "p" and t.string and t.string.startswith("委員：")
            )
            if text
            else None
        )
        member = member_tag.string[3:] if member_tag else ""
        return VideoEntry(url=self._prepend_domain_name(link), member=member)

    def _prepend_domain_name(self, url: str) -> str:
        if url.startswith("http"):
            return url
        return parse.urljoin(self._origin, url)


class VideoReader:
    """Read a video page."""

    @dataclasses.dataclass
    class VideoMeta:
        """Video meta"""

        duration: dt.timedelta = dataclasses.field(default_factory=dt.timedelta)
        start_time: dt.datetime = dataclasses.field(default_factory=dt.datetime)
        end_time: dt.datetime = dataclasses.field(default_factory=dt.datetime)
        playlist: str | None = None

        def __post_init__(self):
            self.start_time = self.start_time.astimezone(dt.timezone.utc)
            self.end_time = self.end_time.astimezone(dt.timezone.utc)

    @property
    def meta(self) -> VideoMeta:
        """Get the video meta"""
        return self._meta

    @property
    def playlist_url(self) -> str | None:
        """Get the playlist url"""
        return self.meta.playlist

    @property
    def playlist(self) -> m3u8.model.M3U8:
        """Get the playlist (m3u8)"""
        if not self._playlist:
            self._playlist = m3u8.load(self.playlist_url)
        return self._playlist

    @property
    def chunks(self) -> m3u8.model.M3U8:  # type(any)
        """Get the chunks (m3u8)"""
        if not self._chunks:
            _chunk: m3u8.model.Segment = self.playlist.playlists[0]
            self._chunks = m3u8.load(parse.urljoin(_chunk.base_uri, _chunk.uri))
        return self._chunks

    @property
    def _taret_duration(self) -> int:
        """Get the target duration (in seconds)"""
        if not self.__target_duration:
            self.__target_duration = int(getattr(self.chunks, "target_duration", 0))
        return self.__target_duration

    @property
    def _clip_chunks(self) -> int:
        """Number of chunks to a clip"""
        return math.ceil(self._clip_size.total_seconds() / self._taret_duration)

    @property
    def clips_count(self) -> int:
        """Get the number of clips"""
        return math.ceil(len(self.chunks.segments) / self._clip_chunks)

    def __init__(
        self, html: str, clip_size: dt.timedelta = dt.timedelta(minutes=30)
    ) -> None:
        self._s = bs4.BeautifulSoup(html, "html.parser")
        self._meta = self._get_meta()
        self._clip_size = clip_size
        self._playlist: m3u8.model.M3U8 | None = None
        self._chunks: m3u8.model.M3U8 | None = None
        self.__target_duration = None

    @classmethod
    def open(cls, url: str) -> "VideoReader":
        """Open a video"""
        res = requests.get(url, headers=_REQUEST_HEADEER, timeout=60)
        if res.status_code != 200:
            raise IOError(f"Failed to read video {url}")
        return cls(res.text)

    def set_clip_size(self, clip_size: dt.timedelta) -> None:
        """Set the clip size"""
        self._clip_size = clip_size

    def _get_meta(self) -> str | None:
        scripts = self._s.find_all("script", type="text/javascript", src=None)
        codes = []
        for script in scripts:
            codes.extend(
                line.strip() for line in "\n".join(script.strings).splitlines()
            )
        movies = [l for l in codes if l and l.startswith("var _movie")]
        if not movies:
            return None
        movie: str = movies[0]
        try:
            json_str = movie.split("('", maxsplit=1)[-1].split("')", maxsplit=1)[0]
        except IndexError:
            return None
        meta = json.loads(json_str)
        meet_date = (
            dt.datetime.strptime(meta["metdat"], "%Y-%m-%d")
            if "metdat" in meta
            else dt.date.today()
        )
        if "lgltim" in meta:
            _st, _et = meta["lgltim"].split("-")
            _st, _et = _st.strip(), _et.strip()
            st = dt.datetime.strptime(_st, "%H:%M:%S").time()
            et = dt.datetime.strptime(_et, "%H:%M:%S").time()
        else:
            st = et = dt.time.min

        if "movtim" in meta:
            h, m, s = meta["movtim"].split(":")
            duration = dt.timedelta(hours=int(h), minutes=int(m), seconds=int(s))
        else:
            duration = dt.timedelta.min

        return VideoReader.VideoMeta(
            duration=duration,
            start_time=dt.datetime.combine(meet_date, st, _TZ),
            end_time=dt.datetime.combine(meet_date, et, _TZ),
            playlist=meta.get("filnam", None),
        )

    def download_mp4(self, clip_index: int = -1) -> str:
        """Download the video
        Args:
            clip_index (int, optional): The clip index to download,
                use -1 to download the full clips. Defaults to -1.
        """
        if clip_index < 0:
            return self._download_mp4()
        idx = clip_index * self._clip_chunks
        if idx >= len(self.chunks.segments):
            raise IndexError(f"clip index {clip_index} out of range")
        chunks = self.chunks.segments[idx : idx + self._clip_chunks]
        if not chunks:
            raise IndexError(f"clip index {clip_index} out of range")
        streams = [ffmpeg.input(parse.urljoin(c.base_uri, c.uri)) for c in chunks]
        _, o = tempfile.mkstemp(suffix=".mp4")
        pipe = ffmpeg.concat(*streams)
        pipe = ffmpeg.output(pipe, o)
        ffmpeg.overwrite_output(pipe).run()
        return o

    def _download_mp4(self) -> str:
        i = ffmpeg.input(self.playlist_url)
        _, o = tempfile.mkstemp(suffix=".mp4")
        out = ffmpeg.output(i, o)
        ffmpeg.overwrite_output(out).run()
        return o


class DocumentReader:
    """Read a document(doc, pdf) to text."""

    @property
    def content(self) -> str:
        """Get the content"""
        return self._content

    def __init__(self, url: str, content: str) -> None:
        self._content = content
        self._url = url

    @classmethod
    def open(cls, url: str) -> "DocumentReader":
        """Open a document"""
        parsed_url = parse.urlparse(url)
        suffix = pathlib.Path(parsed_url.path).suffix
        if suffix == ".pdf":
            return cls(url, cls._pdf2txt(url))
        elif suffix == ".doc":
            return cls(url, cls._doc2txt(url))

    @staticmethod
    def _pdf2txt(url: str) -> str:
        parsed_url = parse.urlparse(url)
        filename = parsed_url.path.split("/")[-1]
        res = requests.get(url, headers=_REQUEST_HEADEER, stream=True, timeout=1800)
        res.raise_for_status()

        with tempfile.TemporaryDirectory() as temp_dir:
            fp = pathlib.Path(temp_dir) / filename
            with fp.open("wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            return textract.process(fp, method="pdfminer").decode("utf-8")

    @staticmethod
    def _doc2txt(url: str) -> str:
        request = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(
            request, params.CLOUD_DOC2TXT_API.value
        )
        api_url = parse.urljoin(params.CLOUD_DOC2TXT_API.value, "doc2txt")
        res = requests.get(
            api_url,
            headers={
                "Authorization": "Bearer " + token,
            },
            params={"url": parse.quote_plus(url)},
            timeout=1800,
            stream=True,
        )
        res.raise_for_status()
        buff = io.BytesIO()
        for chunk in res.iter_content(chunk_size=8192):
            buff.write(chunk)
        return buff.getvalue().decode("utf-8")
