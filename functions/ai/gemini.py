"""Gemini module"""

# pylint: disable=protected-access,no-member
import abc
import dataclasses
import datetime as dt
import io
import itertools
import json
import pathlib
import urllib.parse
import uuid
from collections.abc import Iterable
from typing import Any, Generic, NamedTuple, Optional, TypeVar

import firebase_admin  # type: ignore
import pytz  # type: ignore
import requests  # type: ignore
import utils
import vertexai  # type: ignore
from cloudevents.http.event import CloudEvent
from firebase_admin import firestore, storage
from firebase_functions.options import SupportedRegion
from google.api_core.exceptions import InvalidArgument, NotFound
from google.cloud import aiplatform, bigquery
from google.cloud.firestore import FieldFilter  # type: ignore
from google.cloud.storage import Blob  # type: ignore
from legislature import models
from params import EMBEDDING_MODEL
from vertexai.generative_models import Part  # type: ignore
from vertexai.generative_models import GenerativeModel, SafetySetting
from vertexai.preview.language_models import TextEmbeddingModel  # type: ignore

_REGION = SupportedRegion.US_CENTRAL1
_BUCKET = "gemini-batch"
_TZ = pytz.timezone("Asia/Taipei")

GEMINI_COLLECTION = "gemini"

GEMINI_REGION = _REGION
GEMINI_BUCKET = _BUCKET

T = TypeVar("T")


class MeetSpeech(NamedTuple):
    meet: models.Meeting
    speech: models.Video


@dataclasses.dataclass
class EmbeddingQuery:
    doc_path: str
    content: str


@dataclasses.dataclass
class EmbeddingResult:
    doc_path: str
    embedding: list[float]


@dataclasses.dataclass
class BatchEmbeddingJob:
    uid: str
    job_id: str  # Vertex AI batch job ID


PREDICTION_JOB_AUDIO_TRANSCRIPT = "transcript"
PREDICTION_JOB_DOC_SUMMARY = "summary"
PREDICTION_JOB_SPEECHES_SUMMARY = "speeches"


@dataclasses.dataclass
class BatchPredictionJob:
    name: str
    uid: str
    job_type: str
    source: str  # bigquery source table
    destination: str  # bigquery destination table
    finished: bool = False
    submit_time: dt.datetime = dataclasses.field(
        default_factory=lambda: dt.datetime.now(tz=_TZ)
    )


class PredictionQuery(abc.ABC):

    @abc.abstractmethod
    def to_request(self) -> dict[str, Any]:
        raise NotImplementedError


class GeminiBatchEmbeddingJob:
    """Gemini Batch Embedding Job"""

    _JOB_PREFIX = "embedding_"

    @property
    def _document_name(self) -> str:
        return self._JOB_PREFIX + self._uid

    @utils.simple_cached_property
    def _job(self) -> aiplatform.BatchPredictionJob | None:
        if self._job_id is None:
            return None
        try:
            return aiplatform.BatchPredictionJob(self._job_id)
        except (NotFound, InvalidArgument):
            return None

    @property
    def _gcs_output_path(self) -> str | None:
        if (
            self._job is None or self._job.output_info is None
        ):  # pylint: disable=no-member
            return None
        outdir = self._job.output_info.gcs_output_directory
        if not outdir:
            return None
        return urllib.parse.urlparse(outdir).path.strip("/")

    @utils.simple_cached_property
    def _job_id(self) -> str | None:
        doc = self._db.collection(GEMINI_COLLECTION).document(self._document_name).get()
        if doc.exists:
            job = BatchEmbeddingJob(**doc.to_dict())
            return job.job_id
        return None

    def __init__(self, uid: str):
        app: firebase_admin.App = firebase_admin.get_app()
        vertexai.init(project=app.project_id, location=_REGION.value)
        self._uid = uid
        self._bucket = storage.bucket(_BUCKET)
        self._db = firestore.client()

    @classmethod
    def create(cls, uid: str) -> "GeminiBatchEmbeddingJob":
        """Create a new job with the given uid."""
        return cls(uid)

    @classmethod
    def load(cls, file_path: str) -> Optional["GeminiBatchEmbeddingJob"]:
        """Load a job from the given GCS file path to the prediction results."""
        file_path = file_path.strip("/")
        parts = pathlib.PurePath(file_path).parts
        if len(parts) < 2 or parts[0] != "embeddings":
            return None
        job = cls(parts[1])
        outdir = job._gcs_output_path
        if outdir is None or not file_path.startswith(outdir):
            return None
        return job

    def submit(self, queries: list[EmbeddingQuery]):
        """Submit an async job to Gemini on Vertex AI for batch embedding."""
        contents = [json.dumps({"content": q.content}) for q in queries]
        content_blob = self._bucket.blob(f"embeddings/{self._uid}/content.jsonl")
        content_blob.upload_from_string("\n".join(contents))

        docs = [q.doc_path for q in queries]
        docs_blob = self._bucket.blob(f"embeddings/{self._uid}/docs.json")
        docs_blob.upload_from_string(json.dumps(docs, indent=2))

        gcs_source = f"gs://{self._bucket.name}/{content_blob.name}"
        gcs_destination_prefix = f"gs://{self._bucket.name}/embeddings/{self._uid}"

        model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL.value)
        batch_job = aiplatform.BatchPredictionJob.create(
            model_name=model._model_resource_name,
            job_display_name=f"embedding_{self._uid}",
            gcs_source=gcs_source,
            gcs_destination_prefix=gcs_destination_prefix,
            sync=False,
            model_parameters={"output_dimensionality": 768},
        )
        batch_job.wait_for_resource_creation()
        job_model = BatchEmbeddingJob(
            uid=self._uid,
            job_id=batch_job.name,
        )
        self._db.collection(GEMINI_COLLECTION).document(self._document_name).set(
            dataclasses.asdict(job_model)
        )

    def results(self) -> list[EmbeddingResult]:
        """Read the prediction results from GCS."""
        if self._gcs_output_path is None:
            raise IOError(f"Can't read {self._uid} results from GCS.")
        prediction_blobs: list[Blob] = self._bucket.list_blobs(
            prefix=self._gcs_output_path
        )
        embeddings: list[list[float]] = []
        for blob in prediction_blobs:
            blob_path = pathlib.PurePath(blob.name)
            if blob_path.suffix != ".jsonl":
                continue
            embeddings.extend(
                self._read_prediction(line)
                for line in blob.download_as_text().splitlines()
            )
        docs_blob = self._bucket.blob(f"embeddings/{self._uid}/docs.json")
        docs = json.loads(docs_blob.download_as_text())
        assert len(docs) == len(embeddings)
        return [
            EmbeddingResult(doc, embedding) for doc, embedding in zip(docs, embeddings)
        ]

    def _read_prediction(self, line: str) -> list[float]:
        data = json.loads(line)
        predictions = data.get("predictions", [])
        if not predictions:
            return []
        return predictions[0].get("embeddings", {}).get("values", [])


VIDEO_SUMMARY_PROMPT = """\
請根據影片實際發生的內容，以繁體中文作出詳盡的事件介紹
"""


class GeminiVideoSummaryJob:

    def __init__(self, gs_url: str):
        app: firebase_admin.App = firebase_admin.get_app()
        vertexai.init(project=app.project_id, location=_REGION.value)
        self._url = gs_url

    def run(self) -> str | None:
        model = GenerativeModel(model_name="gemini-1.5-flash")
        response = model.generate_content(
            [VIDEO_SUMMARY_PROMPT, Part.from_uri(self._url, mime_type="video/mp4")]
        )
        return response.text


class GeminiSpeechSummaryJob:

    def __init__(self, member: str, gs_url: str):
        app: firebase_admin.App = firebase_admin.get_app()
        vertexai.init(project=app.project_id, location=_REGION.value)
        self._member = member
        self._url = gs_url

    def run(self) -> str | None:
        model = GenerativeModel(model_name="gemini-1.5-flash")
        response = model.generate_content(
            [
                f"影片中的立法委員是 {self._member}。\n",
                VIDEO_SUMMARY_PROMPT,
                Part.from_uri(self._url, mime_type="video/mp4"),
            ]
        )
        return response.text


class GeminiBatchPredictionJob(abc.ABC, Generic[T]):

    DATASET = "gemini"

    @utils.simple_cached_property
    def source_table(self) -> str:
        table_id = f"prediction-{self.job_type}-source-{self._uid}"
        dataset_ref = self._client.dataset(self.DATASET)
        table_ref = dataset_ref.table(table_id)
        table = bigquery.Table(table_ref, schema=self.schema)
        table = self._client.create_table(table, exists_ok=True)
        return table.full_table_id.replace(":", ".")

    @property
    def source_table_url(self) -> str:
        return f"bq://{self.source_table}"

    @property
    def destination_table(self) -> str:
        return f"{self.project}.{self.DATASET}.prediction-{self.job_type}-destination-{self._uid}"

    @property
    def destination_table_url(self) -> str:
        return f"bq://{self.destination_table}"

    @property
    def model(self) -> str:
        return "publishers/google/models/gemini-1.5-pro-001"

    @property
    def project(self) -> str:
        return self._project_id

    @property
    def bq_load_config(self) -> bigquery.LoadJobConfig:
        return bigquery.LoadJobConfig(
            schema=self.schema,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )

    def __init__(self, uid: str):
        app: firebase_admin.App = firebase_admin.get_app()
        vertexai.init(project=app.project_id, location=_REGION.value)
        self._client = bigquery.Client(project=app.project_id)
        self._uid = uid
        self._app = app
        self._project_id = app.project_id
        self._db = firestore.client()
        self._bucket = storage.bucket(_BUCKET)

    @classmethod
    def from_bq_event(cls, event: CloudEvent):
        resource: str | None = event.get("resourcename")
        if not resource:
            raise ValueError(f"Need bigquery event, got {event}.")
        tokens = resource.strip("/").split("/")
        attributes = {k: v for k, v in zip(tokens[0::2], tokens[1::2])}
        project = attributes["projects"]
        dateset = attributes["datasets"]
        table = attributes["tables"]
        uri = f"bq://{project}.{dateset}.{table}"
        db = firestore.client()
        query = (
            db.collection(GEMINI_COLLECTION)
            .where(filter=FieldFilter("destination", "==", uri))
            .limit(1)
        )
        results = query.get()
        if not results:
            raise ValueError(f"Can't find job write to {uri}")
        job = BatchPredictionJob(**results[0].to_dict())
        return cls(job.uid)

    def write_queries(self, queries: list[PredictionQuery]):
        rows_to_inserts = [q.to_request() for q in queries]
        for batch in itertools.batched(rows_to_inserts, 50):
            jsonl = "\n".join(json.dumps(r) for r in batch)
            uid = uuid.uuid4().hex
            blob = self._bucket.blob(f"predictions/{self._uid}/{uid}")
            blob.upload_from_string(jsonl, timeout=600)
            del jsonl
            uri = f"gs://{self._bucket.name}/{blob.name}"
            load_job = self._client.load_table_from_uri(
                uri,
                self.source_table,
                location=GEMINI_REGION,
                job_config=self.bq_load_config,
                timeout=600,
            )
            load_job.result(timeout=600)
        while rows_to_inserts:
            del rows_to_inserts[0]

    def submit(self) -> BatchPredictionJob:
        token = self._app.credential.get_access_token().access_token
        response = requests.post(
            f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self.project}/locations/us-central1/batchPredictionJobs",
            json={
                "displayName": f"prediction-{self.job_type}-{self._uid}",
                "model": self.model,
                "inputConfig": {
                    "instancesFormat": "bigquery",
                    "bigquerySource": {"inputUri": self.source_table_url},
                },
                "outputConfig": {
                    "predictionsFormat": "bigquery",
                    "bigqueryDestination": {"outputUri": self.destination_table_url},
                },
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        if not response.ok:
            raise RuntimeError(response.text)
        data: dict[str, Any] = response.json()
        name = data.get("name", None)
        if not name:
            raise RuntimeError("fail to create batch prediction job.")
        job = BatchPredictionJob(
            name=name,
            uid=self._uid,
            job_type=self.job_type,
            source=self.source_table_url,
            destination=self.destination_table_url,
        )
        doc_ref = self._db.collection(GEMINI_COLLECTION).document(self._uid)
        doc_ref.set(dataclasses.asdict(job))
        return job

    def mark_as_done(self):
        doc_ref = self._db.collection(GEMINI_COLLECTION).document(self._uid)
        doc = doc_ref.get()
        if not doc.exists:
            raise RuntimeError(f"Job {self._uid} doesn't exist.")
        job = BatchPredictionJob(**doc.to_dict())
        job.finished = True
        doc_ref.set(dataclasses.asdict(job))

    def list_results(self, skip_invalid_row: bool = True) -> Iterable[T | None]:
        page_token = ""
        fields = [s for s in self.schema if s.name != "request"] + [
            bigquery.SchemaField("response", "STRING"),
            bigquery.SchemaField("status", "STRING"),
        ]
        while page_token is not None:
            row_iter = self._client.list_rows(
                self.destination_table,
                max_results=50,
                page_token=page_token,
                selected_fields=fields,
                timeout=300,
            )
            for row in row_iter:
                v = self.parse_row(row)
                if v is None and not skip_invalid_row:
                    raise ValueError(f"Invalid row {row}")
                elif v is not None:
                    yield self.parse_row(row)
            page_token = row_iter.next_page_token

    @abc.abstractmethod
    def parse_row(self, row: bigquery.Row) -> T | None:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def schema(self) -> list[bigquery.SchemaField]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def job_type(self) -> str:
        raise NotImplementedError


@dataclasses.dataclass
class DocumentSummaryQuery(PredictionQuery):
    doc_path: str
    content: str

    def to_request(self) -> dict[str, Any]:
        return {
            "request": {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": "請根據下述的內容，以繁體中文做出詳盡的人物及事件介紹。"
                            },
                            {"text": self.content},
                        ],
                    }
                ]
            },
            "doc_path": self.doc_path,
        }


@dataclasses.dataclass
class TranscriptSummaryQuery(PredictionQuery):
    doc_path: str
    content: str
    member: str

    def to_request(self) -> dict[str, Any]:
        return {
            "request": {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": f"逐字稿中的立法委員是 {self.member}。\n",
                            },
                            {"text": "請根據下述的內容，以繁體中文做出總結。"},
                            {"text": self.content},
                        ],
                    }
                ]
            },
            "doc_path": self.doc_path,
        }


@dataclasses.dataclass
class DocumentSummaryResult:
    doc_path: str
    text: str


class GeminiBatchDocumentSummaryJob(GeminiBatchPredictionJob[DocumentSummaryResult]):

    def parse_row(self, row: bigquery.Row) -> DocumentSummaryResult | None:
        doc_path = row.get("doc_path", None)
        if doc_path is None:
            return None
        payload = row.get("response")
        if not payload:
            return None
        response: list[dict[str, Any]] = json.loads(payload)
        if len(response) != 1:
            return None
        parts = response[0].get("content", {}).get("parts", [])
        if not parts:
            return None
        text = parts[0].get("text", "")
        if not text:
            return None
        return DocumentSummaryResult(doc_path, text)

    @property
    def schema(self) -> list[bigquery.SchemaField]:
        return [
            bigquery.SchemaField("request", "JSON", mode="REQUIRED"),
            bigquery.SchemaField("doc_path", "STRING"),
        ]

    @property
    def job_type(self) -> str:
        return PREDICTION_JOB_DOC_SUMMARY


@dataclasses.dataclass
class AudioTranscriptQuery(PredictionQuery):
    doc_path: str
    audio: bytes  # audio base64 encoded string

    def to_request(self) -> dict[str, Any]:
        return {
            "request": {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": "Please transcribe the audio using zh-TW as the language."
                            },
                            {
                                "inlineData": {
                                    "mimeType": "audio/mp3",
                                    "data": str(self.audio, "utf-8"),
                                }
                            },
                        ],
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "object",
                        "properties": {
                            "subtitles": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"text": {"type": "string"}},
                                    "required": ["text"],
                                },
                            }
                        },
                    },
                    "maxOutputTokens": 8192,
                },
                "safetySettings": [
                    {
                        "category": SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        "threshold": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        "threshold": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                ],
            },
            "doc_path": self.doc_path,
        }


@dataclasses.dataclass
class AudioTranscriptResult:
    doc_path: str
    transcript: str


class GeminiBatchAudioTranscriptJob(GeminiBatchPredictionJob[AudioTranscriptResult]):

    @property
    def schema(self) -> list[bigquery.SchemaField]:
        return [
            bigquery.SchemaField("request", "JSON", mode="REQUIRED"),
            bigquery.SchemaField("doc_path", "STRING"),
        ]

    @property
    def job_type(self) -> str:
        return PREDICTION_JOB_AUDIO_TRANSCRIPT

    def parse_row(self, row: bigquery.Row) -> AudioTranscriptResult | None:
        doc_path = row.get("doc_path", None)
        if doc_path is None:
            raise ValueError(f"Can't find doc_path in row {row}")
        response = row.get("response", "[]")
        if not response:
            return None
        candidates = json.loads(response)
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None
        try:
            data = json.loads(parts[0].get("text", "{}"))
            transcript = "\n".join(
                subtitle.get("text", "") for subtitle in data.get("subtitles", [])
            )
            return AudioTranscriptResult(doc_path, transcript)
        except json.JSONDecodeError:
            return AudioTranscriptResult(doc_path, "")


@dataclasses.dataclass
class SpeechesSummaryQuery(PredictionQuery):
    speeches: list[MeetSpeech]
    doc_path: str

    def _speeches_markdown(self) -> str:
        buff = io.StringIO()
        for item in self.speeches:
            if not item.speech.transcript:
                continue
            buff.write(f"# {item.meet.meeting_name}\n\n")
            buff.write(f"- 時間: {item.meet.meeting_date_desc}\n")
            buff.write(f"- 委員會: {item.meet.meeting_unit}\n")
            buff.write(f"- 質詢委員: {item.speech.member}\n")
            buff.write(f"- 影片:{item.speech.url}\n")
            buff.write("- 逐字稿\n\n")
            buff.write(
                "\n".join([f"\t{line}" for line in item.speech.transcript.splitlines()])
            )
            buff.write("\n\n")
        return buff.getvalue()

    def to_request(self) -> dict[str, Any]:
        return {
            "request": {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    "將相似的內容主題分組並以中文(zh-TW)進行摘要，確保每個摘要涵蓋獨特的主題，避免重複。在摘要中加入註釋，詳細解釋各主題的細節、重點或相關資訊。注意:\n"
                                    "1. 避免重複的主題。 每個 topicName 應該是獨一無二的。\n"
                                    "2. 用委員會的主題來分類，減少同一個委員會的重複主題。\n"
                                    "3. 詳細說明細節。 在 details 數組中提供豐富的資訊和見解\n"
                                    "4. 在 referenceVideos 數組中提供參考的影片，內容接近就好，不需要完全一致。\n"
                                    "5. 著重在事件描述，不要帶入人名。\n"
                                    "6. 請確保主題數量不超過 10 個\n\n"
                                )
                            },
                            {"text": self._speeches_markdown()},
                        ],
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "object",
                        "properties": {
                            "topics": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "topicName": {
                                            "type": "string",
                                            "description": "The name or title of the topic.",
                                        },
                                        "details": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "description": "Details or remarks related to the topic.",
                                            },
                                        },
                                        "referenceVideos": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "format": "uri",
                                            },
                                            "description": "List of reference videos related to the topic.",
                                        },
                                    },
                                    "required": [
                                        "topicName",
                                        "details",
                                        "referenceVideos",
                                    ],
                                },
                            }
                        },
                    },
                    "temperature": 0.5,
                    "maxOutputTokens": 8192,
                },
                "safetySettings": [
                    {
                        "category": SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        "threshold": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        "threshold": SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                ],
            },
            "doc_path": self.doc_path,
        }


@dataclasses.dataclass
class SpeechesSummary:
    doc_path: str
    remarks: list[models.SpeechTopicRemark] = dataclasses.field(default_factory=list)


class GeminiBatchSpeechesSummaryJob(GeminiBatchPredictionJob[SpeechesSummary]):

    @property
    def schema(self) -> list[bigquery.SchemaField]:
        return [
            bigquery.SchemaField("request", "JSON", mode="REQUIRED"),
            bigquery.SchemaField("doc_path", "STRING"),
        ]

    @property
    def job_type(self) -> str:
        return PREDICTION_JOB_SPEECHES_SUMMARY

    def parse_row(self, row: bigquery.Row) -> SpeechesSummary | None:
        doc_path = row.get("doc_path", None)
        if doc_path is None:
            return None
        response = row.get("response", "[]")
        if not response:
            return None
        candidates = json.loads(response)
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None
        try:
            data = json.loads(parts[0].get("text", "{}"))
            summary = data.get("topics", [])
            remarks = [
                models.SpeechTopicRemark(
                    topic=remark.get("topicName", ""),
                    details=remark.get("details", []),
                    video_urls=remark.get("referenceVideos", []),
                )
                for remark in summary
            ]
            return SpeechesSummary(doc_path, remarks)
        except json.JSONDecodeError:
            return None


# TODO: improve transcript's readability
# PROMPT: 加入標點符號並修改冗言贅字，適當分段來增加可讀性。
