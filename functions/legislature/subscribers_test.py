import unittest
from unittest import mock
from legislature.subscribers import on_receive_bigquery_batch_predictions


@unittest.skip("manual")
def test_on_receive_bigquery_batch_predictions():
    mock_event = mock.MagicMock()
    mock_event.get.return_value = (
        "projects/taiwan-legislative-search/datasets/gemini/tables/output-test"
    )
    on_receive_bigquery_batch_predictions(mock_event)
