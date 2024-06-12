# pylint: disable=unused-wildcard-import, wildcard-import
"""
Cloud Functions for Firebase for Python.
Deploy with `firebase deploy`
"""
import firebase_admin
from legislature.legislative_parser import *
from firebase_admin import credentials
import params

cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {"storageBucket": params.STORAGE_BUCKET.value})
