"""Module to download content from Wiki"""

import functools
import io
from typing import Any

import pandas as pd
import requests  # type: ignore
from wiki import models

WIKI_ZH_API = "https://zh.wikipedia.org/w/api.php"
_WIKI_API_VERSION = 2
_DEFAULT_TIMEOUT = 10


class WikiPageReader:

    def __init__(self, page: str):
        self._page = page

    @functools.cached_property
    def sections(self) -> list[models.WikiSection]:
        res = requests.get(
            WIKI_ZH_API,
            params={
                "action": "parse",
                "format": "json",
                "page": self._page,
                "prop": "sections",
                "formatversion": _WIKI_API_VERSION,
            },
            timeout=_DEFAULT_TIMEOUT,
        )
        res.raise_for_status()
        data: dict = res.json()
        sections: list[dict[str, Any]] = data.get("parse", {}).get("sections", [])
        return [models.WikiSection.from_dict(s) for s in sections]

    def get_section_text(self, section_index: int) -> str:
        res = requests.get(
            WIKI_ZH_API,
            params={
                "action": "parse",
                "format": "json",
                "page": self._page,
                "prop": "text",
                "section": section_index,
                "formatversion": _WIKI_API_VERSION,
            },
            timeout=_DEFAULT_TIMEOUT,
        )
        data: dict[str, Any] = res.json()
        return data.get("parse", {}).get("text", "")

    def get_section_links(self, section_index: int) -> list[models.WikiLink]:
        res = requests.get(
            WIKI_ZH_API,
            params={
                "action": "parse",
                "format": "json",
                "page": self._page,
                "prop": "links",
                "section": section_index,
                "formatversion": _WIKI_API_VERSION,
            },
            timeout=_DEFAULT_TIMEOUT,
        )
        data: dict[str, Any] = res.json()
        links: list[dict[str, Any]] = data.get("parse", {}).get("links", [])
        return [models.WikiLink.from_dict(l) for l in links]


class OrganizationReader(WikiPageReader):

    @functools.cached_property
    def directors_section(self) -> str | None:
        if not self._director_section_id:
            return None
        return self.get_section_text(self._director_section_id)

    @functools.cached_property
    def directors_tables(self) -> list[pd.DataFrame]:
        if not self.directors_section:
            return []
        sio = io.StringIO(self.directors_section)
        return pd.read_html(sio)

    @functools.cached_property
    def _director_section_id(self) -> int | None:
        candidates = ["歷任院長", "歷任首長", "歷任"]
        for sec in self.sections:
            for c in candidates:
                if c in sec.line:
                    return sec.index
        return None


def get_organizations() -> list[str]:
    r = WikiPageReader("中華民國中央行政機關")
    sections = [sec for sec in r.sections if sec.line == "機關列表"]
    if not sections:
        return []
    section = sections[0]
    links = r.get_section_links(section.index)
    return [link.title for link in links if link.exists]
