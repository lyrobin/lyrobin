# pylint: disable=unused-wildcard-import, wildcard-import
"""
Cloud Functions for Firebase for Python.
Deploy with `firebase deploy`
"""
import firebase_admin  # type: ignore
from legislature.legislative_parser import *
from legislature.crons import *
from legislature.subscribers import *
from legislature.tasks import *
from firebase_admin import credentials
import params

cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {"storageBucket": params.STORAGE_BUCKET.value})
