"""Script to backup data and export them for local development."""

import argparse
import collections
import contextlib
import datetime as dt
import os

import firebase_admin  # type: ignore
from google.cloud import firestore  # type: ignore
from legislature import models
from search import client as search_client
from utils import testings, timeutil

FIRESTORE_EMULATOR_HOST = "FIRESTORE_EMULATOR_HOST"
DEFAULT_EMULATOR_HOST = "127.0.0.1:8080"
BACKUP_LIMIT = 50

INDEX_TARGETS = {
    search_client.DocType.MEETING: models.MEETING_COLLECT,
    search_client.DocType.PROCEEDING: models.PROCEEDING_COLLECT,
    search_client.DocType.MEETING_FILE: models.FILE_COLLECT,
    search_client.DocType.ATTACHMENT: models.ATTACH_COLLECT,
    search_client.DocType.VIDEO: models.SPEECH_COLLECT,
    search_client.DocType.MEMBER: models.MEMBER_COLLECT,
}


@contextlib.contextmanager
def run_in_prod():
    host = os.environ.pop(FIRESTORE_EMULATOR_HOST, None)
    client = firestore.Client()
    try:
        yield client
    finally:
        client.close()
        os.environ[FIRESTORE_EMULATOR_HOST] = host


@contextlib.contextmanager
def run_in_emulator():
    os.environ[FIRESTORE_EMULATOR_HOST] = DEFAULT_EMULATOR_HOST
    client = firestore.Client()
    try:
        yield client
    finally:
        client.close()


def backup_directors():
    docs: dict[str, dict] = {}
    with run_in_prod() as client:
        directors = client.collection("directors").stream()
        for doc in directors:
            docs[doc.reference.path] = doc.to_dict()
    with run_in_emulator() as client:
        for path, data in docs.items():
            client.document(path).set(data)


def backup_hot_keywords():
    docs: dict[str, dict] = {}
    with run_in_prod() as client:
        hot_keywords = (
            client.collection("hot_keywords")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(1)
            .stream()
        )
        for doc in hot_keywords:
            docs[doc.reference.path] = doc.to_dict()
    with run_in_emulator() as client:
        for path, data in docs.items():
            client.document(path).set(data)


def backup_meetings():
    docs: dict[str, dict] = {}
    with run_in_prod() as client:
        meetings = (
            client.collection("meetings")
            .order_by("meeting_date_start", direction=firestore.Query.DESCENDING)
            .limit(BACKUP_LIMIT)
            .stream()
        )
        for idx, doc in enumerate(meetings):
            docs[doc.reference.path] = doc.to_dict()
            docs.update(dump_children_recursively(doc.reference))
            print(f"Backup meeting {idx + 1} / {BACKUP_LIMIT}")
    with run_in_emulator() as client:
        for path, data in docs.items():
            client.document(path).set(data)


def backup_members():
    term = timeutil.get_legislative_yuan_term(dt.datetime.now(tz=models.MODEL_TIMEZONE))
    docs: dict[str, dict] = {}
    with run_in_prod() as client:
        members = (
            client.collection("members")
            .where(
                filter=firestore.FieldFilter("terms", "array_contains_any", [str(term)])
            )
            .stream()
        )
        for doc in members:
            member = models.Legislator.from_dict(doc.to_dict())
            print(f"Backup member {member.name}")
            docs[doc.reference.path] = doc.to_dict()
            docs.update(dump_children_recursively(doc.reference))
    with run_in_emulator() as client:
        for path, data in docs.items():
            client.document(path).set(data)


def backup_news_report():
    docs: dict[str, dict] = {}
    with run_in_prod() as client:
        news_reports = (
            client.collection("news_reports")
            .order_by("report_date", direction=firestore.Query.DESCENDING)
            .limit(10)
            .stream()
        )
        for doc in news_reports:
            docs[doc.reference.path] = doc.to_dict()
    with run_in_emulator() as client:
        for path, data in docs.items():
            client.document(path).set(data)


def backup_proceedings():
    docs: dict[str, dict] = {}
    with run_in_prod() as client:
        proceedings = (
            client.collection("proceedings")
            .order_by("created_date", direction=firestore.Query.DESCENDING)
            .limit(BACKUP_LIMIT)
            .stream()
        )
        for idx, doc in enumerate(proceedings):
            print(f"Backup proceeding {idx + 1} / {BACKUP_LIMIT}")
            docs[doc.reference.path] = doc.to_dict()
            docs.update(dump_children_recursively(doc.reference))
    with run_in_emulator() as client:
        for path, data in docs.items():
            client.document(path).set(data)


def dump_children_recursively(ref: firestore.DocumentReference) -> dict[str, dict]:
    docs: dict[str, dict] = {}
    queue = collections.deque([ref])
    while queue:
        current = queue.popleft()
        children = current.collections()
        for collection in children:
            for doc in collection.limit(BACKUP_LIMIT).stream():
                docs[doc.reference.path] = doc.to_dict()
                queue.append(doc.reference)
    return docs


def backup_topics():
    docs: dict[str, dict] = {}
    with run_in_prod() as client:
        topics = (
            client.collection("topics")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(BACKUP_LIMIT)
            .stream()
        )
        for idx, doc in enumerate(topics):
            print(f"Backup topic {idx + 1} / {BACKUP_LIMIT}")
            docs[doc.reference.path] = doc.to_dict()
    with run_in_emulator() as client:
        for path, data in docs.items():
            client.document(path).set(data)


def backup_weekly():
    docs: dict[str, dict] = {}
    with run_in_prod() as client:
        weekly = (
            client.collection("weekly")
            .order_by("report_date", direction=firestore.Query.DESCENDING)
            .limit(10)
            .stream()
        )
        for doc in weekly:
            docs[doc.reference.path] = doc.to_dict()
    with run_in_emulator() as client:
        for path, data in docs.items():
            client.document(path).set(data)


def backup_all():
    backup_directors()
    backup_hot_keywords()
    backup_meetings()
    backup_members()
    backup_news_report()
    backup_proceedings()
    backup_topics()
    backup_weekly()


def build_search_index():
    se = search_client.DocumentSearchEngine(api_key="xyz")
    se.create_collection(search_client.DOCUMENT_SCHEMA_V1)
    se.update_collection(search_client.DOCUMENT_SCHEMA_V2)
    se.update_collection(search_client.DOCUMENT_SCHEMA_V3)
    se.update_collection(search_client.DOCUMENT_SCHEMA_V4)
    for doc_type, collection in INDEX_TARGETS.items():
        print(f"Indexing {doc_type} from {collection}")
        index_documents(se, doc_type, collection)
    se.snapshot("/data/typesense-data-snapshot")


def index_documents(
    se: search_client.DocumentSearchEngine,
    doc_type: search_client.DocType,
    collection: str,
):
    with run_in_emulator() as client:
        docs = client.collection_group(collection).stream()
        for doc in docs:
            se.index(doc.reference.path, doc_type)


@testings.disable_background_triggers
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--firestore", action="store_true")
    parser.add_argument("--search", action="store_true")
    args = parser.parse_args()

    firebase_admin.initialize_app()

    if args.firestore:
        print("Backup all firestore data")
        backup_all()
    if args.search:
        print("Build search index")
        build_search_index()


if __name__ == "__main__":
    main()
