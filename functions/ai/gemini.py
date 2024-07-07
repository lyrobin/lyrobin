"""Gemini module"""

# pylint: disable=protected-access,no-member
import dataclasses
import json
import pathlib
import urllib.parse
from typing import Any, Optional
import itertools

import firebase_admin  # type: ignore
import requests  # type: ignore
import utils
import vertexai  # type: ignore
from firebase_admin import firestore, storage
from firebase_functions.options import SupportedRegion
from google.api_core.exceptions import InvalidArgument, NotFound
from google.cloud import aiplatform, bigquery
from google.cloud.storage import Blob  # type: ignore
from params import EMBEDDING_MODEL
from vertexai.generative_models import GenerativeModel, Part  # type: ignore
from vertexai.preview.language_models import TextEmbeddingModel  # type: ignore

_REGION = SupportedRegion.US_CENTRAL1
_BUCKET = "gemini-batch"
_COLLECTION = "gemini"

GEMINI_REGION = _REGION
GEMINI_BUCKET = _BUCKET


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
        doc = self._db.collection(_COLLECTION).document(self._document_name).get()
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
        self._db.collection(_COLLECTION).document(self._document_name).set(
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
