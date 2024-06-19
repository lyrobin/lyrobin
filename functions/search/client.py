"""Module of search engine clients."""

import dataclasses
import datetime as dt
from enum import Enum

import typesense
from firebase_admin import firestore
from google.cloud.firestore import DocumentReference, DocumentSnapshot
from legislature import models
from params import TYPESENSE_HOST, TYPESENSE_PORT, TYPESENSE_PROTOCOL

DOCUMENT_SCHEMA_V1 = {
    "name": "documents",
    "fields": [
        {"name": "collection", "type": "string", "facet": True, "optional": True},
        {
            "name": "embedding",
            "type": "float[]",
            "num_dim": 768,
            "optional": True,
        },
        {"name": ".*", "type": "auto"},
    ],
}


SUMMARY_MAX_LENGTH = 1000
CONTENT_MAX_LENGTH = 10000
QUERY_LIMIT = 100


class DocType(Enum):
    """Enum for document types."""

    MEETING = models.Meeting.__name__.lower()
    PROCEEDING = models.Proceeding.__name__.lower()
    VIDEO = models.Video.__name__.lower()
    MEETING_FILE = models.MeetingFile.__name__.lower()
    ATTACHMENT = models.Attachment.__name__.lower()


@dataclasses.dataclass
class Document:
    """Typesense Document class."""

    id: str = ""
    doc_type: str = ""
    name: str = ""
    summary: str = ""
    content: str = ""
    created_date: dt.datetime = dataclasses.field(default=dt.datetime.min)
    vector: list[float] = dataclasses.field(default_factory=list)
    metadata: dict[str, str] = dataclasses.field(default_factory=dict)

    def to_dict(self):
        """Convert Document to dict."""
        fields = dataclasses.fields(self)
        data = dataclasses.asdict(self)
        result = {}
        for field in fields:
            if field.name in ["created_date", "metadata"]:
                continue
            name, val = field.name, data.get(field.name, None)
            if not val:
                continue
            result[name] = val
        if self.created_date.replace(tzinfo=None) > dt.datetime.min:
            result["created_date"] = int(
                self.created_date.replace(tzinfo=dt.timezone.utc).timestamp()
            )
        for k, v in self.metadata.items():
            if v:
                result[k] = v
        return result


class SearchResult:

    def __init__(self, result: dict):
        self._result = result

    @property
    def hit_count(self) -> int:
        return self._result["found"]


class DocumentSearchEngine:
    """Document Typesense search engine client."""

    def __init__(
        self,
        host: str = "localhost",
        port: str = "8108",
        protocol: str = "http",
        api_key: str = "",
    ):
        self._client = typesense.Client(
            {
                "nodes": [
                    {
                        "host": host,
                        "port": port,
                        "protocol": protocol,
                    }
                ],
                "api_key": api_key,
                "connection_timeout_seconds": 5,
            }
        )
        self._db = firestore.client()

    @classmethod
    def create(cls, api_key: str):
        """Create a new instance of DocumentSearchEngine with environment variables."""
        return cls(
            host=TYPESENSE_HOST.value,
            port=TYPESENSE_PORT.value,
            protocol=TYPESENSE_PROTOCOL.value,
            api_key=api_key,
        )

    def index(self, doc_path: str, doc_type: DocType):
        """Create a document index."""
        ref = self._db.document(doc_path)
        doc = ref.get()
        if not doc.exists:
            raise FileNotFoundError(f"Can't find {doc_path}.")
        target = self._convert_to_indexable_document(doc, doc_type)
        self._client.collections["documents"].documents.upsert(target.to_dict())

    def query(self, query: str, query_by="*", filter_by="") -> SearchResult:
        """Query documents."""
        res = self._client.collections["documents"].documents.search(
            {
                "q": query,
                "query_by": query_by,
                "include_fields": "id",
                "highlight_fields": "name,summary",
                "filter_by": filter_by,
            }
        )
        return SearchResult(res)

    def create_collection(self, schema: dict):
        """Create a collection.
        Use this function only for the first time to initialize the collection.
        """
        assert "name" in schema and schema["name"] == "documents"
        assert "fields" in schema
        collections = self._client.collections.retrieve()
        if any([collect.get("name", "") == "documents" for collect in collections]):
            return
        self._client.collections.create(schema)

    def drop_collection(self):
        """Drop the collection."""
        collections = self._client.collections.retrieve()
        if not any([collect.get("name", "") == "documents" for collect in collections]):
            return
        self._client.collections["documents"].delete()

    def _convert_to_indexable_document(
        self, doc: DocumentSnapshot, doc_type: DocType
    ) -> Document:
        target: Document
        match doc_type:
            case DocType.MEETING:
                target = self._meeting_to_doc(doc)
            case DocType.PROCEEDING:
                target = self._proceeding_to_doc(doc)
            case DocType.MEETING_FILE:
                target = self._meet_file_to_doc(doc)
            case DocType.ATTACHMENT:
                target = self._attachment_to_doc(doc)
            case _:
                raise TypeError(f"Unsupported doc type {doc_type}.")
        return target

    def _meeting_to_doc(self, doc: DocumentSnapshot) -> Document:
        ref: DocumentReference = doc.reference
        m: models.Meeting = models.Meeting.from_dict(doc.to_dict())
        return Document(
            id=ref.path,
            doc_type=models.Meeting.__name__.lower(),
            name=m.meeting_name,
            summary=m.ai_summary[0:SUMMARY_MAX_LENGTH],
            content=m.meeting_content[0:CONTENT_MAX_LENGTH],
            created_date=m.meeting_date_start,
            vector=m.embedding_vector,
            metadata={
                "term": m.term,
                "period": m.session_period,
                "chairman": m.co_chairman,
                "meeting_unit": m.meeting_unit,
            },
        )

    def _proceeding_to_doc(self, doc: DocumentSnapshot) -> Document:
        ref: DocumentReference = doc.reference
        m: models.Proceeding = models.Proceeding.from_dict(doc.to_dict())
        return Document(
            id=ref.path,
            doc_type=models.Proceeding.__name__.lower(),
            name=m.name,
            summary=m.ai_summary[0:SUMMARY_MAX_LENGTH],
            created_date=m.created_date,
            vector=m.embedding_vector,
            metadata={
                "status": m.status,
                "proposers": m.proposers,
                "sponsors": m.sponsors,
            },
        )

    def _meet_file_to_doc(self, doc: DocumentSnapshot) -> Document:
        ref: DocumentReference = doc.reference
        m: models.MeetingFile = models.MeetingFile.from_dict(doc.to_dict())

        def get_create_date() -> dt.datetime:
            if not ref.path.startswith(models.MEETING_COLLECT):
                return dt.datetime.min
            meet_ref = self._db.document("/".join(ref.path.split("/")[0:2]))
            meet_doc = meet_ref.get()
            if not meet_doc.exists:
                return dt.datetime.min
            meet: models.Meeting = models.Meeting.from_dict(meet_doc.to_dict())
            return meet.meeting_date_start

        return Document(
            id=ref.path,
            doc_type=models.MeetingFile.__name__.lower(),
            name=m.name,
            summary=m.ai_summary[0:SUMMARY_MAX_LENGTH],
            created_date=get_create_date(),
            vector=m.embedding_vector,
        )

    def _attachment_to_doc(self, doc: DocumentSnapshot) -> Document:
        ref: DocumentReference = doc.reference
        m: models.Attachment = models.Attachment.from_dict(doc.to_dict())

        def get_create_date() -> dt.datetime:
            if ref.path.startswith(models.PROCEEDING_COLLECT):
                _doc = self._db.document("/".join(ref.path.split("/")[0:2])).get()
                if not _doc.exists:
                    return dt.datetime.min
                return models.Proceeding.from_dict(_doc.to_dict()).created_date
            else:
                return dt.datetime.min

        return Document(
            id=ref.path,
            doc_type=models.Attachment.__name__.lower(),
            name=m.name,
            summary=m.ai_summary,
            created_date=get_create_date(),
            vector=m.embedding_vector,
        )
