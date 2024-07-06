import dataclasses
import json
import pathlib
import unittest
import uuid
from unittest import mock
import logging

from ai import gemini
from firebase_admin import firestore, storage  # type: ignore
from utils import testings

logger = logging.getLogger(__name__)


def _test_file(name: str) -> pathlib.Path:
    return pathlib.Path(__file__).parent / "testdata" / name


class TestGeminiBatchEmbeddingJob(unittest.TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._db = firestore.client()
        self._bucket = storage.bucket()
        self._batch_job_patcher = mock.patch("ai.gemini.aiplatform.BatchPredictionJob")
        self._mock_batch_job_cls = self._batch_job_patcher.start()
        self._mock_batch_job = mock.MagicMock()
        self._mock_batch_job_cls.return_value = self._mock_batch_job

    def tearDown(self) -> None:
        super().tearDown()
        self._batch_job_patcher.stop()

    @mock.patch("ai.gemini.aiplatform.BatchPredictionJob.create")
    @testings.disable_background_triggers
    def test_create(self, mock_create: mock.MagicMock):
        uid = uuid.uuid4().hex
        mock_create.return_value.name = uid
        job = gemini.GeminiBatchEmbeddingJob.create(uid)

        job.submit([gemini.EmbeddingQuery("meetings/1/files/1", "text/plain")])

        mock_create.assert_called_once()
        job_doc = self._db.document(f"gemini/embedding_{uid}").get()
        assert job_doc.exists
        job_model = gemini.BatchEmbeddingJob(**job_doc.to_dict())
        assert job_model.uid == uid
        assert job_model.job_id == uid
        content_blob = self._bucket.blob(f"embeddings/{uid}/content.jsonl")
        docs_blob = self._bucket.blob(f"embeddings/{uid}/docs.json")
        assert content_blob.exists()
        assert docs_blob.exists()

    @testings.disable_background_triggers
    def test_load(self):
        uid = uuid.uuid4().hex
        self._db.document(f"gemini/embedding_{uid}").set(
            dataclasses.asdict(gemini.BatchEmbeddingJob(uid=uid, job_id=uid))
        )
        docs = ["meetings/1/files/1", "meetings/1/files/2"]
        self._bucket.blob(f"embeddings/{uid}/docs.json").upload_from_string(
            json.dumps(docs)
        )
        prediction_path = f"embeddings/{uid}/prediction/000000000000.jsonl"
        self._bucket.blob(prediction_path).upload_from_string(
            _test_file("000000000000.jsonl").read_text()
        )
        self._mock_batch_job.output_info.gcs_output_directory = (
            f"gs://{self._bucket.name}/{prediction_path}"
        )

        job = gemini.GeminiBatchEmbeddingJob.load(prediction_path)
        results = job.results()

        self.assertSequenceEqual([r.doc_path for r in results], docs)
        assert len(results[0].embedding) == 768
        assert all(isinstance(v, float) for v in results[0].embedding)
        assert len(results[1].embedding) == 768
        assert all(isinstance(v, float) for v in results[1].embedding)


class TestGeminiVideoSummaryJob(unittest.TestCase):

    @unittest.skip("for manual test")
    def test_run(self):
        job = gemini.GeminiVideoSummaryJob(
            "gs://taiwan-legislative-search.appspot.com/videos/0089757e842c31968a8bd475f9ccd1d4/clips/0.mp4"
        )
        summary = job.run()
        logger.debug(summary)
        self.assertIsNotNone(summary)


if __name__ == "__main__":
    unittest.main()
