"""
This module contains the models for the Firestore database.
"""

# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-member
import dataclasses
import datetime as dt
import uuid
from typing import TypeVar, Type, Any
from urllib import parse
import json

import deepdiff  # type: ignore
import pytz  # type: ignore
import utils
from google.cloud.firestore_v1.vector import Vector
from legislature import LEGISLATURE_MEETING_URL

# Collection Constants
MEETING_COLLECT = "meetings"
IVOD_COLLECT = "ivods"
FILE_COLLECT = "files"
PROCEEDING_COLLECT = "proceedings"
ATTACH_COLLECT = "attachments"
# Sub-collection - ivod
VIDEO_COLLECT = "videos"
SPEECH_COLLECT = "speeches"
MEMBER_COLLECT = "members"

T = TypeVar("T", bound="FireStoreDocument")
_TZ = pytz.timezone("Asia/Taipei")

MODEL_TIMEZONE = _TZ

_PRIMITIVE_TYPES = (int, float, str, bool, type(None))


class IntField:
    """
    A field that stores an integer.
    """

    def __init__(self, *, default: int | None = None):
        self._default = default

    def __set_name__(self, _: object, name: str) -> None:
        self._name = "_" + name
        self._default_name = name

    def __get__(self, instance: object, _: type) -> int:
        if instance is None and self._default is not None:
            return self._default
        return getattr(instance, self._name, self._default or 0)

    def __set__(self, instance: object, value: Any) -> None:
        if isinstance(value, type(self)):
            setattr(instance, self._name, value._default)
            return
        try:
            setattr(instance, self._name, int(value))
        except TypeError as err:
            raise TypeError(
                f"{self._default_name} must be an integer, not {value}"
            ) from err


class OptionalIntField(IntField):
    """
    A field that stores an integer or None.
    """

    def __init__(self):
        super().__init__(default=None)

    def __set__(self, instance: object, value: Any) -> None:
        if value is None or value == "null":
            setattr(instance, self._name, None)
            return
        super().__set__(instance, value)


class DateTimeField:
    """
    A field that stores a datetime.
    """

    def __init__(self, *, default: dt.datetime | None = None):
        if default and default.tzinfo is None:
            default = default.replace(tzinfo=_TZ).astimezone(dt.timezone.utc)
        self._default = (
            default
            if default is not None
            else dt.datetime(year=1, month=1, day=1, tzinfo=dt.timezone.utc)
        )

    def __set_name__(self, _: object, name: str) -> None:
        self._name = "_" + name
        self._default_name = name

    def __get__(self, instance: object, _: type) -> dt.datetime:
        if instance is None:
            return self._default
        return getattr(instance, self._name)

    def __set__(self, instance: object, value: str | dt.datetime | None) -> None:
        if value is None:
            setattr(instance, self._name, dt.datetime.min)
        elif isinstance(value, type(self)):
            setattr(instance, self._name, value._default)
        elif isinstance(value, dt.datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=_TZ)
            setattr(instance, self._name, value.astimezone(dt.timezone.utc))
        elif isinstance(value, str):
            setattr(
                instance,
                self._name,
                dt.datetime.strptime(value, "%Y/%m/%d %H:%M")
                .replace(tzinfo=_TZ)
                .astimezone(dt.timezone.utc),
            )
        else:
            raise TypeError(
                f"{self._default_name} must be a dt.datetime or str, not {value}"
            )


@dataclasses.dataclass(match_args=False)
class FireStoreDocument:
    """
    A Firestore document.
    """

    _SPECIAL_FIELDS = ["document_id", "embedding_vector"]

    document_id: str = ""
    ai_summarized: bool = False
    ai_summarized_at: DateTimeField = DateTimeField()
    ai_summary: str = ""
    embedding_vector: list[float] = dataclasses.field(default_factory=list)
    embedding_updated_at: DateTimeField = DateTimeField()
    last_update_time: DateTimeField = DateTimeField()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return not deepdiff.DeepDiff(self.asdict(), other.asdict(), ignore_order=True)

    @classmethod
    def from_dict(cls: Type[T], data: dict | None) -> T:
        """
        Creates a new instance from a dictionary.
        """
        if data is None:
            raise ValueError("data must be a dict.")
        fields = {field.name for field in dataclasses.fields(cls)}
        _data = {utils.camel_to_snake(k): v for k, v in data.items()}
        if isinstance((vector := _data.get("embedding_vector", None)), Vector):
            _data["embedding_vector"] = list(vector)
        return cls(**{k: v for k, v in _data.items() if k in fields})

    def _sanitize_fields(self):
        """Sanitize fields.
        Make sure the value of field has the same type as it's declared.
        A field with inconsistent type may cause deepcopy to fail.
        """
        for field in dataclasses.fields(self):
            if field.type not in _PRIMITIVE_TYPES:
                continue
            val = getattr(self, field.name, None)
            if val is None:
                continue
            if field.type == type(val):
                continue
            setattr(self, field.name, field.type(val))

    def asdict(self) -> dict:
        """
        Returns a dictionary representation of the object.
        """

        def is_empty(value):
            if value is None:
                return True
            elif isinstance(value, str):
                return not value
            elif isinstance(value, dt.datetime):
                return value == dt.datetime.min
            elif (
                isinstance(value, list)
                or isinstance(value, tuple)
                or isinstance(value, set)
                or isinstance(value, dict)
            ):
                return not value
            else:
                return False

        self._sanitize_fields()
        data = {
            k: v
            for k, v in dataclasses.asdict(self).items()
            if k not in self._SPECIAL_FIELDS and not is_empty(v)
        }
        if self.embedding_vector:
            data["embedding_vector"] = Vector(self.embedding_vector)
        return data


@dataclasses.dataclass
class Meeting(FireStoreDocument):
    """
    A meeting.
    """

    term: OptionalIntField = OptionalIntField()
    session_period: OptionalIntField = OptionalIntField()
    session_times: OptionalIntField = OptionalIntField()
    meeting_times: OptionalIntField = OptionalIntField()
    meeting_no: str = ""
    meeting_date_desc: str = ""
    meeting_date_start: DateTimeField = DateTimeField()
    meeting_date_end: DateTimeField = DateTimeField()
    meeting_room: str = ""
    meeting_unit: str = ""
    joint_committee: str = ""
    meeting_name: str = ""
    meeting_content: str = ""
    co_chairman: str = ""
    attend_legislator: str = ""

    def __post_init__(self):
        self.document_id = self.meeting_no
        date_parts = self.meeting_date_desc.split(" ")
        if len(date_parts) != 2:
            return
        date, time_desc = date_parts
        y, m, d = date.split("/")
        y = str(int(y) + 1911)
        t = dt.datetime(int(y), int(m), int(d), 0, 0)
        time_range = time_desc.split("-")
        if time_range:
            sh, sm = time_range[0].split(":")
            st = dt.timedelta(hours=int(sh), minutes=int(sm))
            self.meeting_date_start = t + st
        if len(time_range) > 1 and time_range[1]:
            eh, em = time_range[1].split(":")
            if int(eh) >= 24:
                et = dt.timedelta(days=1, minutes=int(em))
            else:
                et = dt.timedelta(hours=int(eh), minutes=int(em))
            self.meeting_date_end = t + et

    def get_url(self):
        """
        Returns the URL of the meeting.
        """
        url = "/".join([LEGISLATURE_MEETING_URL.value, str(self.meeting_no), "details"])
        d = self.meeting_date_desc.split(" ", maxsplit=1)[0]
        return url + "?" + f"meetingDate={d}"


@dataclasses.dataclass
class IVOD(FireStoreDocument):
    """
    An IVOD.
    """

    name: str = ""
    url: str = ""

    def __post_init__(self):
        parsed_url = parse.urlparse(self.url)
        meet_id = parse.parse_qs(parsed_url.query).get("Meet", [])
        if not meet_id:
            raise ValueError(f"Invalid IVOD URL: {self.url}")
        if isinstance(meet_id, list):
            meet_id = meet_id[0]
        self.document_id = meet_id


@dataclasses.dataclass
class Video(FireStoreDocument):
    """
    A video.
    """

    name: str = ""
    url: str = ""
    member: str | None = None
    playlist: str = ""
    start_time: DateTimeField = DateTimeField()
    clips: list[str] = dataclasses.field(default_factory=list)
    audios: list[str] = dataclasses.field(default_factory=list)
    transcript: str = ""
    has_transcript: bool = False
    transcript_updated_at: DateTimeField = DateTimeField()

    def __post_init__(self):
        self.document_id = uuid.uuid3(uuid.NAMESPACE_URL, self.url).hex


@dataclasses.dataclass
class Attachment(FireStoreDocument):
    """An attachment."""

    name: str = ""
    url: str = ""
    full_text: str = ""

    def __post_init__(self):
        self.url = self.url.replace("\\", "/")
        self.document_id = uuid.uuid3(uuid.NAMESPACE_URL, self.url).hex


@dataclasses.dataclass
class MeetingFile(Attachment):
    """
    An attachment to a meeting.
    """


@dataclasses.dataclass
class Proceeding(FireStoreDocument):
    """
    A proceeding.
    """

    name: str = ""
    url: str = ""
    bill_no: str = ""
    related_bills: list[str] = dataclasses.field(default_factory=list)
    proposers: list[str] = dataclasses.field(default_factory=list)
    sponsors: list[str] = dataclasses.field(default_factory=list)
    status: str = ""
    progress: list[dict] = dataclasses.field(default_factory=list)
    created_date: DateTimeField = DateTimeField()

    def __post_init__(self):
        self.document_id = self.bill_no


@dataclasses.dataclass
class SpeechTopicRemark:
    topic: str
    details: list[str]
    video_url: str

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "SpeechTopicRemark":
        return cls(**json.loads(data))


@dataclasses.dataclass
class Legislator(FireStoreDocument):
    name: str = ""
    ename: str = ""
    sex: str = ""
    party: str = ""
    area: str = ""
    onboard_date: DateTimeField = DateTimeField()
    degree: str = ""
    avatar: str = ""
    leave: bool = False
    terms: list[int] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        self.document_id = uuid.uuid3(
            uuid.NAMESPACE_URL, f"{self.name}.{self.ename}"
        ).hex
