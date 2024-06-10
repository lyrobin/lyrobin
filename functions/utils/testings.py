"""Testings module."""

import os
import types
import unittest
import functools

import requests
from firebase_functions import logger


def is_using_emulators():
    """Check if we're using firebase emulators."""
    return os.environ.get("FIREBASE_EMULATOR_HUB") is not None


def require_firestore_emulator(func):
    """Require firestore emulator."""
    if not isinstance(func, types.FunctionType):
        raise TypeError("This decorator can only be used on functions")

    def wrapper(*args, **kwargs):
        if not is_using_emulators():
            raise unittest.SkipTest("Require firebase emulator")
        if os.environ.get("FIRESTORE_EMULATOR_HOST") is None:
            raise unittest.SkipTest(
                (
                    "Require firestore emulator, ",
                    "consider setting FIRESTORE_EMULATOR_HOST environment variable",
                )
            )
        return func(*args, **kwargs)

    return wrapper


def skip_when_using_emulators(func):
    """Skip a function if we're using firebase emulators."""

    def wrapper(*args, **kwargs):
        if is_using_emulators():
            logger.info("Skipping function because we're using firebase emulators.")
            return
        return func(*args, **kwargs)

    return wrapper


def skip_when_no_network(func):
    """Skip a function if we're not connected to the internet."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        access = os.environ.get("NETWORK_TEST", "False").lower() in (
            "true",
            "1",
        )
        if not access:
            raise unittest.SkipTest("Require internet access")
        return func(*args, **kwargs)

    return wrapper


def skip_when_no_credential(func):
    """Skip a test when there is no credential.
    
        To create a service account and have your application use it for API access, run:
            $ gcloud iam service-accounts create my-account
            $ gcloud iam service-accounts keys create key.json \
                --iam-account=my-account@my-project.iam.gserviceaccount.com
            $ export GOOGLE_APPLICATION_CREDENTIALS=key.json
            $ ./my_application.sh
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)
        if not cred:
            raise unittest.SkipTest(
                "Require credential, set GOOGLE_APPLICATION_CREDENTIALS env."
            )
        return func(*args, **kwargs)

    return wrapper


def disable_background_triggers(func):
    """Disable background triggers."""

    def wrapper(*args, **kwargs):
        if not is_using_emulators():
            return func(*args, **kwargs)
        requests.put(
            "http://localhost:4400/functions/disableBackgroundTriggers", timeout=60
        )
        try:
            return func(*args, **kwargs)
        finally:
            requests.put(
                "http://localhost:4400/functions/enableBackgroundTriggers", timeout=60
            )

    return wrapper


def assert_contains_exactly(got: list, want: list):
    """Assert that got contains exactly want."""
    assert len(got) == len(want)
