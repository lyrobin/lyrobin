"""Gemini module"""

# pylint: disable=protected-access,no-member
import abc
import dataclasses
import datetime as dt
import itertools
import json
import pathlib
import urllib.parse
import uuid
from collections.abc import Iterable
from typing import Any, Generic, Optional, TypeVar

import firebase_admin  # type: ignore
import pytz  # type: ignore
import requests  # type: ignore
import utils
import vertexai  # type: ignore
from firebase_admin import firestore, storage
from firebase_functions.options import SupportedRegion
from google.api_core.exceptions import InvalidArgument, NotFound
from google.cloud import aiplatform, bigquery
from google.cloud.storage import Blob  # type: ignore
from params import EMBEDDING_MODEL
from vertexai.generative_models import (  # type: ignore
    GenerativeModel,
    Part,
    SafetySetting,
)
from vertexai.preview.language_models import TextEmbeddingModel  # type: ignore
from cloudevents.http.event import CloudEvent
from google.cloud.firestore import FieldFilter

_REGION = SupportedRegion.US_CENTRAL1
_BUCKET = "gemini-batch"
_TZ = pytz.timezone("Asia/Taipei")

GEMINI_COLLECTION = "gemini"

GEMINI_REGION = _REGION
GEMINI_BUCKET = _BUCKET

T = TypeVar("T")


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


class BatchPredictionQuery(abc.ABC):

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


@dataclasses.dataclass
class BatchSummaryQuery:
    doc_path: str
    content: str

    def to_request(self) -> dict[str, Any]:
        return {
            "request": json.dumps(
                {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": "請根據下述的內容，以繁體中文做出詳盡的人物及事件介紹"
                                },
                                {"text": self.content},
                            ],
                        }
                    ]
                }
            ),
            "doc_path": self.doc_path,
        }


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
        uri = f"bq://{attributes["projects"]}.{attributes["datasets"]}.{attributes["tables"]}"
        db = firestore.client()
        query = db.collection(GEMINI_COLLECTION).where(filter=FieldFilter("destination", "==", uri)).limit(1)
        results = query.get()
        if not results:
            raise ValueError(f"Can't find job write to {uri}")
        job = BatchPredictionJob(**results[0].to_dict())
        return cls(job.uid)

    def write_queries(self, queries: list[BatchPredictionQuery]):
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


class GeminiBatchDocumentSummaryJob:

    MODEL = "publishers/google/models/gemini-1.5-flash-001"
    DATESET = "gemini"
    SCHEMA = [
        bigquery.SchemaField("request", "JSON", mode="REQUIRED"),
        bigquery.SchemaField("doc_path", "STRING"),
    ]

    def __init__(self, uid: str):
        app: firebase_admin.App = firebase_admin.get_app()
        vertexai.init(project=app.project_id, location=_REGION.value)
        self._client = bigquery.Client(project=app.project_id)
        self._uid = uid
        self._project = app.project_id
        self._token = app.credential.get_access_token().access_token

    def run(self, queries: list[BatchSummaryQuery]) -> bool:
        # TODO: create a better table name for debugging
        input_uri = self._write_quires(queries)
        output_uri = f"{self._project}.{self.DATESET}.output-summary-{self._uid}"
        response = requests.post(
            f"https://us-central1-aiplatform.googleapis.com/v1/projects/{self._project}/locations/us-central1/batchPredictionJobs",
            json={
                "displayName": f"summary-{self._uid}",
                "model": self.MODEL,
                "inputConfig": {
                    "instancesFormat": "bigquery",
                    "bigquerySource": {"inputUri": f"bq://{input_uri}"},
                },
                "outputConfig": {
                    "predictionsFormat": "bigquery",
                    "bigqueryDestination": {"outputUri": f"bq://{output_uri}"},
                },
            },
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=60,
        )
        return response.ok

    def _write_quires(self, queries: list[BatchSummaryQuery]) -> str:
        table_id = f"input-summary-{self._uid}"
        dataset_ref = self._client.dataset(self.DATESET)
        table_ref = dataset_ref.table(table_id)
        table = bigquery.Table(table_ref, schema=self.SCHEMA)
        table = self._client.create_table(table, exists_ok=True)
        rows_to_inserts = [q.to_request() for q in queries]
        resource = f"{self._project}.{self.DATESET}.{table_id}"
        for batch in itertools.batched(rows_to_inserts, 10):
            self._client.insert_rows_json(resource, batch, timeout=300)
        return resource


@dataclasses.dataclass
class BatchAudioTranscriptQuery(BatchPredictionQuery):
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
class BatchAudioTranscriptResult:
    doc_path: str
    transcript: str


class GeminiBatchAudioTranscriptJob(
    GeminiBatchPredictionJob[BatchAudioTranscriptResult]
):

    @property
    def schema(self) -> list[bigquery.SchemaField]:
        return [
            bigquery.SchemaField("request", "JSON", mode="REQUIRED"),
            bigquery.SchemaField("doc_path", "STRING"),
        ]

    @property
    def job_type(self) -> str:
        return PREDICTION_JOB_AUDIO_TRANSCRIPT

    def parse_row(self, row: bigquery.Row) -> BatchAudioTranscriptResult | None:
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
            return BatchAudioTranscriptResult(doc_path, transcript)
        except json.JSONDecodeError:
            return None
