"""Update firestore schema."""

import os
import sys
import argparse
import json
import dataclasses
from typing import Type
import itertools
import multiprocessing

from legislature import models
import firebase_admin  # type: ignore
from firebase_admin import credentials, firestore
from google.cloud.firestore import DocumentSnapshot  # type: ignore

FIRESTORE_ENVIRONMENTS = [
    "FIRESTORE_EMULATOR_HOST",
    "FIREBASE_AUTH_EMULATOR_HOST",
    "FIREBASE_STORAGE_EMULATOR_HOST",
    "STORAGE_EMULATOR_HOST",
    "FIREBASE_EMULATOR_HUB",
    "FUNCTIONS_EMULATOR_HOST",
]


@dataclasses.dataclass
class CollectionInfo:
    name: str
    doc_class: Type[models.FireStoreDocument]
    is_group: bool = False


COLLECTIONS = {
    c.name: c
    for c in [
        CollectionInfo(models.MEETING_COLLECT, models.Meeting),
        CollectionInfo(models.VIDEO_COLLECT, models.Video, is_group=True),
        CollectionInfo(models.SPEECH_COLLECT, models.Video, is_group=True),
        CollectionInfo(models.ATTACH_COLLECT, models.Attachment, is_group=True),
        CollectionInfo(models.FILE_COLLECT, models.MeetingFile, is_group=True),
        CollectionInfo(models.PROCEEDING_COLLECT, models.Proceeding),
    ]
}


def reset_env():
    for env in FIRESTORE_ENVIRONMENTS:
        if env in os.environ:
            del os.environ[env]


def init_firebase():
    with open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"], "r", encoding="utf-8") as f:
        cred = credentials.Certificate(json.load(f))
    try:
        firebase_admin.initialize_app(
            cred, {"storageBucket": "taiwan-legislative-search.appspot.com"}
        )
    except ValueError:
        pass


def update_schema(name: str):
    init_firebase()

    db = firestore.client()

    c = COLLECTIONS[name]

    rows: list[DocumentSnapshot]
    if c.is_group:
        rows = db.collection_group(name).stream()
    else:
        rows = db.collection(name).get()

    for batch in itertools.batched(rows, 50):
        b = db.batch()
        for row in batch:
            m = c.doc_class.from_dict(row.to_dict())
            b.update(row.reference, m.asdict())
        b.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prod", action="store_true", default=False)
    args = parser.parse_args()

    if args.prod:
        reset_env()

    with multiprocessing.Pool(10) as pool:
        pool.map(update_schema, COLLECTIONS.keys())


if __name__ == "__main__":
    main()
