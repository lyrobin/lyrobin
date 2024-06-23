"""Gemini module"""

# pylint: disable=protected-access,no-member
import dataclasses
import json
import pathlib
import urllib.parse
from typing import Optional

import firebase_admin  # type: ignore
import vertexai  # type: ignore
from firebase_admin import firestore, storage
from firebase_functions.options import SupportedRegion
from google.api_core.exceptions import InvalidArgument, NotFound
from google.cloud import aiplatform
from google.cloud.storage import Blob  # type: ignore
from params import EMBEDDING_MODEL
from vertexai.preview.language_models import TextEmbeddingModel  # type: ignore
import utils

_REGION = SupportedRegion.ASIA_EAST1
_COLLECTION = "gemini"


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
        self._bucket = storage.bucket()
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

        gcs_source = (
            f"gs://{self._bucket.name}/embeddings/{self._uid}/{content_blob.name}"
        )

        model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL.value)
        batch_job = aiplatform.BatchPredictionJob.create(
            model_name=model._model_resource_name,
            job_display_name=f"embedding_{self._uid}",
            gcs_source=gcs_source,
            gcs_destination_prefix=f"embeddings/{self._uid}",
            sync=False,
            model_parameters={"output_dimensionality": 768},
        )

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
