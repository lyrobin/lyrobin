"""
This module contains the models for the Firestore database.
"""

import abc
import contextlib

# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-member
import dataclasses
import datetime as dt
import functools
import json
import uuid
from typing import Any, Sequence, Type, TypeVar, Optional
from urllib import parse

import deepdiff  # type: ignore
import pytz  # type: ignore
import utils
from firebase_admin import storage  # type: ignore
from google.cloud import firestore  # type: ignore
from google.cloud.firestore_v1.vector import Vector
from legislature import LEGISLATURE_MEETING_URL

# Collection Constants
MEETING_COLLECT = "meetings"
IVOD_COLLECT = "ivods"
FILE_COLLECT = "files"
PROCEEDING_COLLECT = "proceedings"
ATTACH_COLLECT = "attachments"
WEEKLY_COLLECT = "weekly"
NEWS_REPORT_COLLECT = "news_reports"
# Sub-collection - general
EMBEDDINGS_COLLECT = "embeddings"
# Sub-collection - ivod
VIDEO_COLLECT = "videos"
SPEECH_COLLECT = "speeches"
MEMBER_COLLECT = "members"
# Sub-collection - legislator
SUMMARY_COLLECT = "summary"
SUMMARY_TOPIC_COLLECT = "topics"

T = TypeVar("T", bound="FireStoreDocument")
K = TypeVar("K", bound="BaseDocument")
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


@dataclasses.dataclass
class BaseDocument(abc.ABC):

    @classmethod
    def from_dict(cls: Type[K], data: dict | None) -> K:
        """
        Creates a new instance from a dictionary.
        """
        if data is None:
            raise ValueError("data must be a dict.")
        fields = {field.name for field in dataclasses.fields(cls)}
        _data = {utils.camel_to_snake(k): v for k, v in data.items()}
        return cls(**{k: v for k, v in _data.items() if k in fields})

    def asdict(self) -> dict:
        """
        Returns a dictionary representation of the object.
        """
        return dataclasses.asdict(self)


@dataclasses.dataclass(match_args=False)
class FireStoreDocument:
    """
    A Firestore document.
    """

    _SPECIAL_FIELDS = ["document_id", "embedding_vector"]

    document_id: str = ""
    embedding_vector: list[float] = dataclasses.field(default_factory=list)
    embedding_updated_at: DateTimeField = DateTimeField()
    last_update_time: DateTimeField = DateTimeField()

    # Full text embeddings
    full_text_embeddings_count: int = 0

    # AI Summary Job
    ai_summarized: bool = False
    ai_summarized_at: DateTimeField = DateTimeField()
    ai_summary_attempts: int = 0
    ai_summary: str = ""

    # Hash Tag Job
    hash_tags: list[str] = dataclasses.field(default_factory=list)
    has_hash_tags: bool = False
    hash_tags_summarized_at: DateTimeField = DateTimeField()
    has_tags_summary_attempts: int = 0

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
    hd_url: str = ""
    member: str | None = None
    playlist: str = ""
    hd_playlist: str = ""
    start_time: DateTimeField = DateTimeField()
    clips: list[str] = dataclasses.field(default_factory=list)
    hd_clips: list[str] = dataclasses.field(default_factory=list)
    audios: list[str] = dataclasses.field(default_factory=list)

    # Transcript Job
    transcript: str = ""
    has_transcript: bool = False
    transcript_updated_at: DateTimeField = DateTimeField()
    transcript_attempts: int = 0

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

    def derive_created_date(self) -> dt.datetime:
        """Derive the created date from the progress if created_date is invalid."""
        if self.created_date > dt.datetime(1911, 1, 1, tzinfo=dt.timezone.utc):
            return self.created_date
        first_date = ""
        for p in self.progress:
            if _date := p.get("date", None):
                first_date = _date
                break
        else:
            return self.created_date
        if len(parts := first_date.split("/")) == 3:
            y, m, d = parts
            return dt.datetime(int(y) + 1911, int(m), int(d), tzinfo=dt.timezone.utc)
        return self.created_date


@dataclasses.dataclass
class SpeechTopicRemark:
    topic: str
    details: list[str]
    video_urls: list[str]

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
    terms: list[str] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        self.document_id = uuid.uuid3(
            uuid.NAMESPACE_URL, f"{self.name}.{self.ename}"
        ).hex


@dataclasses.dataclass
class LegislatorSummary(FireStoreDocument):
    topics: list[str] = dataclasses.field(default_factory=list)
    context_uri: str = ""
    created_at: DateTimeField = DateTimeField()


@dataclasses.dataclass
class LegislatorSummaryTopic(FireStoreDocument):
    title: str = ""
    remarks: list[str] = dataclasses.field(default_factory=list)
    ready: bool = False
    videos: list[str] = dataclasses.field(default_factory=list)
    created_at: DateTimeField = DateTimeField()


@dataclasses.dataclass
class Embedding:
    idx: int
    embedding: list[float] = dataclasses.field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Embedding":
        return cls(data["idx"], list(data["embedding"]))

    def asdict(self) -> dict:
        return {"idx": self.idx, "embedding": Vector(self.embedding)}

    def to_vector(self) -> Vector:
        return Vector(self.embedding)


def update_embeddings(
    ref: firestore.DocumentReference, embeddings: Sequence[Embedding | list[float]]
):
    if not ref.get().exists:
        raise ValueError(f"Document {ref.path} does not exist")
    doc = FireStoreDocument.from_dict(ref.get().to_dict())
    doc.full_text_embeddings_count = len(embeddings)
    embeddings_collect: firestore.CollectionReference = ref.collection(
        EMBEDDINGS_COLLECT
    )

    new_embeddings: list[Embedding] = []
    for i, e in enumerate(embeddings):
        if isinstance(e, Embedding):
            e.idx = i
            new_embeddings.append(e)
        elif isinstance(e, list):
            new_embeddings.append(Embedding(i, e))
        else:
            raise TypeError(f"Invalid embedding type at {i}: {type(e)}")

    for embedding in new_embeddings:
        embeddings_collect.document(str(embedding.idx)).set(
            embedding.asdict(), merge=True
        )
    ref.update(doc.asdict())


def get_embeddings(ref: firestore.DocumentReference) -> list[Embedding]:
    if not ref.get().exists:
        raise ValueError(f"Document {ref.path} does not exist")
    doc = FireStoreDocument.from_dict(ref.get().to_dict())
    if doc.full_text_embeddings_count <= 0:
        return []
    embeddings_collect: firestore.CollectionReference = ref.collection(
        EMBEDDINGS_COLLECT
    )
    embedding_refs = [
        embeddings_collect.document(str(i))
        for i in range(doc.full_text_embeddings_count)
    ]
    if not all(ref.get().exists for ref in embedding_refs):
        raise RuntimeError("Some embeddings do not exist.")
    return [Embedding.from_dict(ref.get().to_dict()) for ref in embedding_refs]


@dataclasses.dataclass
class WeeklyReport(BaseDocument):
    """Weekly report for Legislature Yuan."""

    all_report_uri: str
    transcript_uri: str
    report_date: DateTimeField = DateTimeField()
    titles: list[str] = dataclasses.field(default_factory=list)
    week: int = 0

    def __post_init__(self):
        if not self.all_report_uri.startswith("gs://"):
            raise ValueError(f"Invalid URI: {self.all_report_uri}")
        self.week = self.report_date.isocalendar()[1]

    def all_report_txt(self) -> str:
        """Get the content of the report."""
        bucket, blob_path = utils.parse_gsutil_uri(self.all_report_uri)
        blob = storage.bucket(bucket).blob(blob_path)
        return blob.download_as_text(encoding="utf-8")


@dataclasses.dataclass
class NewsReport(BaseDocument):
    """A news report."""

    title: str
    source_uri: str
    transcript_uri: str
    content: str | None = None
    keywords: list[str] = dataclasses.field(default_factory=list)
    legislators: list[str] = dataclasses.field(default_factory=list)
    report_date: DateTimeField = DateTimeField()
    is_ready: bool = False

    def get_source_text(self) -> str:
        bucket, blob_path = utils.parse_gsutil_uri(self.source_uri)
        blob = storage.bucket(bucket).blob(blob_path)
        return blob.download_as_text(encoding="utf-8")

    def get_transcript_text(self) -> str:
        bucket, blob_path = utils.parse_gsutil_uri(self.transcript_uri)
        blob = storage.bucket(bucket).blob(blob_path)
        return blob.download_as_text(encoding="utf-8")


# Start of data models
class MeetingModel:
    """A model for a meeting."""

    @functools.cached_property
    def value(self) -> Meeting:
        """Get the value of the model."""
        doc = self.ref.get()
        if not doc.exists:
            raise ValueError(f"Document {self.ref.path} does not exist")
        return Meeting.from_dict(doc.to_dict())

    @functools.cached_property
    def proceedings(self) -> list["ProceedingModel"]:
        """Get the proceedings of the meeting."""
        return self._get_proceedings()

    @functools.cached_property
    def speeches(self) -> list["SpeechModel"]:
        """Get the speeches of the meeting."""
        return self._get_speeches()

    @functools.cached_property
    def ivods(self) -> list["IVODModel"]:
        """Get the IVODs of the meeting."""
        return self._get_ivods()

    def __init__(self, ref: firestore.DocumentReference):
        self.ref = ref

    @classmethod
    def from_ref(cls, ref: firestore.DocumentReference) -> "MeetingModel":
        """Build a MeetingModel from a Firestore reference."""
        if not ref.path.startswith(MEETING_COLLECT):
            raise ValueError(f"Invalid collection: {ref.path}")
        parts = ref.path.split("/")
        parent = ref
        for _ in range(0, len(parts) - 2):
            parent = parent.parent
        return cls(parent)

    def _get_proceedings(self) -> list["ProceedingModel"]:
        docs = self.ref.collection(PROCEEDING_COLLECT).stream()
        return [ProceedingModel.from_ref(doc.reference) for doc in docs]

    def _get_speeches(self) -> list["SpeechModel"]:
        ivods: list[firestore.DocumentReference] = [
            doc.reference for doc in self.ref.collection(IVOD_COLLECT).stream()
        ]
        result: list["SpeechModel"] = []
        for ivod in ivods:
            result.extend(
                SpeechModel(doc.reference)
                for doc in ivod.collection(SPEECH_COLLECT).stream()
            )
        return result

    def _get_ivods(self) -> list["IVODModel"]:
        docs = self.ref.collection(IVOD_COLLECT).stream()
        return [IVODModel.from_ref(doc.reference) for doc in docs]


class ProceedingModel:
    """A model for a proceeding."""

    @functools.cached_property
    def value(self) -> Proceeding:
        """Get the value of the model."""
        doc = self.ref.get()
        if not doc.exists:
            raise ValueError(f"Document {self.ref.path} does not exist")
        return Proceeding.from_dict(doc.to_dict())

    @functools.cached_property
    def attachments(self) -> list["AttachmentModel"]:
        """Get the attachments of the proceeding."""
        return self._get_attachments()

    def __init__(self, ref: firestore.DocumentReference):
        self.ref = ref

    @classmethod
    def from_ref(cls, ref: firestore.DocumentReference) -> "ProceedingModel":
        """Build a ProceedingModel from a Firestore reference."""
        if ref.path.startswith(MEETING_COLLECT):
            return cls._from_sub_reference(ref)
        elif ref.path.startswith(PROCEEDING_COLLECT):
            return cls._from_reference(ref)
        else:
            raise ValueError(f"Invalid collection: {ref.path}")

    @classmethod
    def _from_reference(cls, ref: firestore.DocumentReference) -> "ProceedingModel":
        if not ref.path.startswith(PROCEEDING_COLLECT):
            raise ValueError(f"Invalid collection: {ref.path}")
        parts = ref.path.split("/")
        parent = ref
        for _ in range(0, len(parts) - 2):
            parent = parent.parent
        return cls(parent)

    @classmethod
    def _from_sub_reference(cls, ref: firestore.DocumentReference) -> "ProceedingModel":
        """Build a ProceedingModel from a Firestore reference."""
        if not ref.path.startswith(MEETING_COLLECT):
            raise ValueError(f"Invalid collection: {ref.path}")
        parts = ref.path.split("/")
        if len(parts) < 4 or parts[-2] != PROCEEDING_COLLECT:
            raise ValueError(f"Invalid collection: {ref.path}")
        doc = ref.get()
        if not doc.exists:
            raise ValueError(f"Document {ref.path} does not exist")
        m = Proceeding.from_dict(doc.to_dict())
        db = firestore.Client()
        with contextlib.closing(db):
            return cls._from_reference(
                db.document(PROCEEDING_COLLECT + "/" + m.bill_no)
            )

    def _get_attachments(self) -> list["AttachmentModel"]:
        docs = self.ref.collection(ATTACH_COLLECT).stream()
        return [AttachmentModel.from_ref(doc.reference) for doc in docs]


class AttachmentModel:

    @functools.cached_property
    def value(self) -> Attachment:
        doc = self.ref.get()
        if not doc.exists:
            raise ValueError(f"Document {self.ref.path} does not exist")
        return Attachment.from_dict(doc.to_dict())

    def __init__(self, ref: firestore.DocumentReference):
        self.ref = ref

    @classmethod
    def from_ref(cls, ref: firestore.DocumentReference) -> "AttachmentModel":
        if not ref.path.startswith(PROCEEDING_COLLECT):
            raise ValueError(f"Invalid collection: {ref.path}")
        return cls(ref)


class SpeechModel:

    @functools.cached_property
    def value(self) -> Video:
        doc = self.ref.get()
        if not doc.exists:
            raise ValueError(f"Document {self.ref.path} does not exist")
        return Video.from_dict(doc.to_dict())

    @functools.cached_property
    def meeting(self) -> MeetingModel:
        return MeetingModel.from_ref(self.ref)

    def __init__(self, ref: firestore.DocumentReference):
        self.ref = ref


class IVODModel:

    @functools.cached_property
    def value(self) -> IVOD:
        doc = self.ref.get()
        if not doc.exists:
            raise ValueError(f"Document {self.ref.path} does not exist")
        return IVOD.from_dict(doc.to_dict())

    def __init__(self, ref: firestore.DocumentReference):
        self.ref = ref

    @classmethod
    def from_ref(cls, ref: firestore.DocumentReference) -> "IVODModel":
        if not ref.path.startswith(MEETING_COLLECT):
            raise ValueError(f"Invalid collection: {ref.path}")
        return cls(ref)


class LegislatorModel:

    @functools.cached_property
    def value(self) -> Legislator:
        doc = self.ref.get()
        if not doc.exists:
            raise ValueError(f"Document {self.ref.path} does not exist")
        return Legislator.from_dict(doc.to_dict())

    def __init__(self, ref: firestore.DocumentReference):
        self.ref = ref

    @functools.cached_property
    def latest_summary(self) -> Optional["LegislatorSummaryModel"]:
        """Get the latest summary of the legislator."""
        collect: firestore.CollectionReference = self.ref.collection(SUMMARY_COLLECT)
        docs = (
            collect.order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(1)
            .get()
        )
        if not docs:
            return None
        return LegislatorSummaryModel(docs[0].reference)

    def add_summary(self, summary: LegislatorSummary) -> "LegislatorSummaryModel":
        """Add a summary to the legislator."""
        collect: firestore.CollectionReference = self.ref.collection(SUMMARY_COLLECT)
        _, ref = collect.add(summary.asdict())
        return LegislatorSummaryModel(ref)


class LegislatorSummaryModel:

    @functools.cached_property
    def value(self) -> LegislatorSummary:
        doc = self.ref.get()
        if not doc.exists:
            raise ValueError(f"Document {self.ref.path} does not exist")
        return LegislatorSummary.from_dict(doc.to_dict())

    def __init__(self, ref: firestore.DocumentReference):
        self.ref = ref

    @functools.cached_property
    def topics(self) -> list["LegislatorSummaryTopicModel"]:
        """Get the topics of the summary."""
        collect: firestore.CollectionReference = self.ref.collection(
            SUMMARY_TOPIC_COLLECT
        )
        docs = collect.stream()
        return [LegislatorSummaryTopicModel(doc.reference) for doc in docs]

    @property
    def ready(self) -> bool:
        if not self.topics:
            return False
        return all(topic.value.ready for topic in self.topics)

    def add_topic(self, topic: LegislatorSummaryTopic) -> "LegislatorSummaryTopicModel":
        """Add a topic to the summary."""
        collect: firestore.CollectionReference = self.ref.collection(
            SUMMARY_TOPIC_COLLECT
        )
        _, ref = collect.add(topic.asdict())
        return LegislatorSummaryTopicModel(ref)


class LegislatorSummaryTopicModel:

    @functools.cached_property
    def value(self) -> LegislatorSummaryTopic:
        doc = self.ref.get()
        if not doc.exists:
            raise ValueError(f"Document {self.ref.path} does not exist")
        return LegislatorSummaryTopic.from_dict(doc.to_dict())

    def __init__(self, ref: firestore.DocumentReference):
        self.ref = ref

    def save(self):
        """Save the topic."""
        self.ref.update(self.value.asdict())
