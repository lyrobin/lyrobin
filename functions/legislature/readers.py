"""
A module to read a legislative pages.
"""

import dataclasses
import re
from urllib import parse

import bs4
import requests

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
    """A class to represent a video."""

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
        """Get a list of videos."""
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
        links: list[bs4.Tag] = sec.find_all(_is_link_to_bill)

        sec = self._s.find("article", id="section-2")
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
