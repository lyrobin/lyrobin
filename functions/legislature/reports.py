"""Module to generate reports for RAG."""

import datetime as dt
from typing import Any

from typing import Sequence
import io
from legislature import models
import json


def dumps_meetings_report(meetings: Sequence[models.MeetingModel]) -> str:
    buf = io.StringIO()
    for m in sorted(meetings, key=lambda x: x.value.meeting_date_start):
        buf.write(f"# {m.value.meeting_name}\n")
        buf.write(f" - 日期: {m.value.meeting_date_desc}\n")
        buf.write(f" - 委員會: {m.value.meeting_unit}\n")
        buf.write("\n")
        buf.write(f"## 內容\n\n{m.value.meeting_content}\n")
        buf.write("## 委員發言\n")
        for s in m.speeches:
            buf.write(f"### {s.value.member}\n\n")
            buf.write(f"- 時間: {s.value.start_time}\n")
            buf.write(f"- 影片: {s.value.hd_url}\n")
            buf.write("\n")
            buf.write(f"{s.value.transcript}\n")
            buf.write("\n\n")
        buf.write("## 議事錄\n")
        for p in m.proceedings:
            buf.write(f"### {p.value.name}\n")
            attachments = _get_unique_and_not_empty_attachments(
                [a.value for a in p.attachments]
            )
            for a in attachments:
                buf.write(f"#### {a.name}\n")
                buf.write(f"{a.full_text}\n")
                buf.write("\n\n")
    return buf.getvalue()


def dumps_meeting_transcripts(
    meetings: Sequence[models.MeetingModel],
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
) -> str:
    if start is None:
        start = dt.datetime(1911, 1, 1, tzinfo=models.MODEL_TIMEZONE)
    if end is None:
        end = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    buf = io.StringIO()
    for m in sorted(meetings, key=lambda x: x.value.meeting_date_start):
        if len(m.speeches) <= 0:
            continue
        buf.write(f"# {m.value.meeting_name}\n")
        buf.write(f" - 日期: {m.value.meeting_date_desc}\n")
        buf.write(f" - 委員會: {m.value.meeting_unit}\n")
        buf.write("\n")
        buf.write("## 委員發言\n\n")
        for s in m.speeches:
            if not start <= s.value.start_time <= end:
                continue
            buf.write(f"### {s.value.member}\n\n")
            buf.write(f"- 時間: {s.value.start_time}\n")
            buf.write(f"- 影片: {s.value.hd_url}\n")
            buf.write(f"- 發言委員: {s.value.member}\n")
            buf.write("\n")
            buf.write(f"{s.value.transcript}\n")
            buf.write("\n\n")
    return buf.getvalue()


def dump_meeting_transcripts_in_json(
    meetings: Sequence[models.MeetingModel],
    start: dt.datetime | None = None,
    end: dt.datetime | None = None,
) -> str:

    if start is None:
        start = dt.datetime(1911, 1, 1, tzinfo=models.MODEL_TIMEZONE)
    if end is None:
        end = dt.datetime.now(tz=models.MODEL_TIMEZONE)

    result = []
    for m in sorted(meetings, key=lambda x: x.value.meeting_date_start):
        if len(m.speeches) <= 0:
            continue
        meeting_data: dict[str, Any] = {
            "會議名稱": m.value.meeting_name,
            "會議日期": m.value.meeting_date_desc,
            "委員會": m.value.meeting_unit,
            "委員發言": [],
        }
        for s in m.speeches:
            if not start <= s.value.start_time <= end:
                continue
            speech_data = {
                "立法委員": s.value.member,
                "開始時間": s.value.start_time.isoformat(),
                "影片連結": s.value.hd_url,
                "逐字稿": s.value.transcript,
            }
            meeting_data["委員發言"].append(speech_data)
        result.append(meeting_data)

    return json.dumps(result, ensure_ascii=False, indent=2)


def dump_speeches(speeches: Sequence[models.SpeechModel]) -> str:
    """Dump speeches to string."""
    result = []
    for speech in speeches:
        speech_data = {
            "會議名稱": speech.meeting.value.meeting_name,
            "委員會": speech.meeting.value.meeting_unit,
            "立法委員": speech.value.member,
            "開始時間": speech.value.start_time.isoformat(),
            "影片連結": speech.value.hd_url,
            "逐字稿": speech.value.transcript,
        }
        result.append(speech_data)
    return json.dumps(result, ensure_ascii=False, indent=2)


def _get_unique_and_not_empty_attachments(
    attachments: Sequence[models.Attachment],
) -> list[models.Attachment]:
    _attachments = [a for a in attachments if a.full_text]
    results = []
    seen = set()
    for a in _attachments:
        name = a.name.removesuffix("DOC").removesuffix("PDF")
        if name in seen:
            continue
        results.append(a)
        seen.add(name)
    return results
