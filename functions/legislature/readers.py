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


@dataclasses.dataclass
class ProceedingEntry:
    """A class to represent a legislative meeting proceedings."""

    name: str
    url: str
    bill_no: str


@dataclasses.dataclass
class AttachmentEntry:
    """A class to represent a video."""

    name: str
    url: str


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
        cls, url: str, qs: dict[str, any], timeout=60
    ) -> "LegislativeMeetingReader":
        """Open a legislative meeting page."""
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
