"""pytest init"""

import pytest

import firebase_admin
from firebase_admin import credentials


@pytest.fixture(scope="session", autouse=True)
def initialize_test_environment():
    """
    Initialize the test environment.
    """
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)
