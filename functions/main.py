# pylint: disable=unused-wildcard-import, wildcard-import
"""
Cloud Functions for Firebase for Python.
Deploy with `firebase deploy`
"""
import firebase_admin  # type: ignore
import params
from admin.users import *
from firebase_admin import credentials
from legislature.crons import *
from legislature.legislative_parser import *
from legislature.subscribers import *
from legislature.tasks import *

cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {"storageBucket": params.STORAGE_BUCKET.value})
