"""pytest init"""

import os
import pytest

import firebase_admin
from firebase_admin import credentials
from search import client as search_client


@pytest.fixture(scope="session", autouse=True)
def initialize_test_environment():
    """
    Initialize the test environment.
    """
    project = os.environ.get("GCLOUD_PROJECT", "")
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {"storageBucket": f"{project}.appspot.com"})
    se = search_client.DocumentSearchEngine.create(api_key="xyz")
    se.drop_collection()
    se.create_collection(search_client.DOCUMENT_SCHEMA_V1)
