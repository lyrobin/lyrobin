import json
import unittest
from unittest import mock

from ai.batch import common
from firebase_admin import firestore  # type: ignore
from google.cloud.firestore_v1 import vector as firestore_vector
from legislature import models
from utils import testings


class TestCommonBatch(unittest.TestCase):

    @mock.patch("ai.batch.common.gembatch.submit")
    def test_start_generate_hashtags(self, mock_submit: mock.Mock):
        content = "test content"
        doc_path = "test/doc/path"

        common.start_generate_hashtags(content, doc_path)

        mock_submit.assert_called_once()

    def test_on_receive_hashtags(self):
        db = firestore.client()
        ref = db.collection("test").document()
        ref.set(models.FireStoreDocument().asdict())
        mock_response = mock.MagicMock()
        mock_response.text = json.dumps(["#test", "#test2"])

        common.on_receive_hashtags(mock_response, ref.path)

        doc = models.FireStoreDocument.from_dict(ref.get().to_dict())
        self.assertEqual(doc.hash_tags, ["test", "test2"])
        self.assertTrue(doc.has_hash_tags)

    @testings.disable_background_triggers
    @mock.patch("ai.batch.common.gembatch.submit")
    @mock.patch("ai.batch.common.ai_embeddings.get_embedding_vectors_from_text")
    @mock.patch("ai.batch.common.context.attach_directors_background")
    @mock.patch("ai.batch.common.context.attach_legislators_background")
    def test_start_generate_summary_when_no_embeddings(
        self,
        mock_legislators: mock.Mock,
        mock_directors: mock.Mock,
        mock_vectors: mock.Mock,
        mock_submit: mock.Mock,
    ):

        db = firestore.client()
        ref = db.collection("test").document()
        ref.set(models.FireStoreDocument().asdict())
        mock_vectors.return_value = [
            firestore_vector.Vector([0.1, 0.2, 0.3]),
        ]

        common.start_generate_summary(ref, "content")

        mock_legislators.assert_called_once()
        mock_directors.assert_called_once()
        mock_vectors.assert_called_once()
        mock_submit.assert_called_once()

    @testings.disable_background_triggers
    @mock.patch("ai.batch.common.gembatch.submit")
    @mock.patch("ai.batch.common.ai_embeddings.get_embedding_vectors_from_text")
    @mock.patch("ai.batch.common.context.attach_directors_background")
    @mock.patch("ai.batch.common.context.attach_legislators_background")
    def test_start_generate_summary_when_exception(
        self,
        mock_legislators: mock.Mock,
        mock_directors: mock.Mock,
        mock_vectors: mock.Mock,
        mock_submit: mock.Mock,
    ):
        db = firestore.client()
        ref = db.collection("test").document()
        ref.set(models.FireStoreDocument(full_text_embeddings_count=1).asdict())

        common.start_generate_summary(ref, "content")

        mock_legislators.assert_called_once()
        mock_directors.assert_called_once()
        mock_vectors.assert_called_once()
        mock_submit.assert_called_once()
