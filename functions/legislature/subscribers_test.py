import unittest
from unittest import mock
from legislature.subscribers import on_receive_bigquery_batch_predictions
import os


@unittest.skip("manual")
def test_on_receive_bigquery_batch_predictions():
    mock_event = mock.MagicMock()
    mock_event.get.return_value = "projects/taiwan-legislative-search/datasets/gemini/tables/output-summary-d63cb77cecf94d9bbfd6a7ba1a93ce4f"
    on_receive_bigquery_batch_predictions(mock_event)
