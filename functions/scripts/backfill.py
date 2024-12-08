"""Script to backfill data in the database."""

import argparse
import datetime as dt
import functools
import os

import firebase_admin  # type: ignore
import inquirer  # type: ignore
import params
from ai.batch import audio_transcribe
from firebase_admin import firestore  # type: ignore
from google.cloud import firestore as cloud_firestore  # type: ignore
from legislature import legislative_parser as ly_parser
from legislature import models, readers
from search import client as search_client
from utils import firestore as firestore_utils

EMULATOR_ENVS = [
    "FIRESTORE_EMULATOR_HOST",
    "FIREBASE_EMULATOR_HUB",
    "FIREBASE_STORAGE_EMULATOR_HOST",
    "STORAGE_EMULATOR_HOST",
]

INDEX_TARGETS = {
    search_client.DocType.MEETING: models.MEETING_COLLECT,
    search_client.DocType.PROCEEDING: models.PROCEEDING_COLLECT,
    search_client.DocType.MEETING_FILE: models.FILE_COLLECT,
    search_client.DocType.ATTACHMENT: models.ATTACH_COLLECT,
    search_client.DocType.VIDEO: models.SPEECH_COLLECT,
    search_client.DocType.MEMBER: models.MEMBER_COLLECT,
}


def warn_using_emulator(func):
    """Warn the user if they are using the emulator and ask if they want to switch to production."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if any(os.environ.get(env, None) for env in EMULATOR_ENVS):
            print("Warning: Using Firestore emulator.")
            ok = inquirer.confirm("Do you want to switch to production environment?")
            if ok:
                for env in EMULATOR_ENVS:
                    os.environ.pop(env)
        return func(*args, **kwargs)

    return wrapper


def backfill_speeches_segment(args: argparse.Namespace):
    """Backfill the speeches segment."""
    start = dt.datetime.strptime(args.start, "%Y-%m-%d")
    end = dt.datetime.strptime(args.end, "%Y-%m-%d")
    print(f"Backfill speeches segment. (start: {start}, end: {end})")
    db = firestore.client()
    query = (
        db.collection_group(models.SPEECH_COLLECT)
        .where(filter=cloud_firestore.FieldFilter("start_time", ">=", start))
        .where(filter=cloud_firestore.FieldFilter("start_time", "<=", end))
        .order_by("start_time", direction=cloud_firestore.Query.ASCENDING)
        .limit(100)
    )
    counter = 0
    for doc in firestore_utils.iterate_all_documents(query):
        m = models.SpeechModel(doc.reference)
        if m.has_segments:
            continue
        print(f"Backfilling {doc.reference.path} ({m.value.start_time})")
        try:
            audio_transcribe.start_transcribe(m, parse_meta=False)
            counter += 1
        except ValueError as e:
            print(f"Error: {e} ({doc.reference.path})")
            continue
    print(f"Backfilled {counter} speeches.")


@warn_using_emulator
def backfill_search_index(args: argparse.Namespace):
    db = firestore.client()
    se = search_client.DocumentSearchEngine(host=args.host, api_key=args.api_key)
    for doc_type, collection in INDEX_TARGETS.items():
        query = _get_iterable_query(db, collection)
        for doc in firestore_utils.iterate_all_documents(query):
            print(f"Indexing {doc.reference.path} ({doc_type})")
            se.index(doc.reference.path, doc_type)


def _get_iterable_query(
    db: cloud_firestore.Client, collection: str
) -> cloud_firestore.Query:
    match collection:
        case models.MEETING_COLLECT:
            return (
                db.collection(collection)
                .order_by(
                    "meeting_date_start", direction=cloud_firestore.Query.ASCENDING
                )
                .limit(100)
            )
        case models.PROCEEDING_COLLECT:
            return (
                db.collection(collection)
                .order_by("created_date", direction=cloud_firestore.Query.ASCENDING)
                .limit(100)
            )
        case models.FILE_COLLECT | models.ATTACH_COLLECT:
            return (
                db.collection_group(collection)
                .order_by("last_update_time", direction=cloud_firestore.Query.ASCENDING)
                .limit(100)
            )
        case models.SPEECH_COLLECT:
            return (
                db.collection_group(collection)
                .order_by("start_time", direction=cloud_firestore.Query.ASCENDING)
                .limit(100)
            )
        case models.MEMBER_COLLECT:
            return (
                db.collection(collection)
                .order_by("name", direction=cloud_firestore.Query.ASCENDING)
                .limit(100)
            )
        case _:
            raise ValueError(f"Invalid collection: {collection}")


@warn_using_emulator
def backfill_speeches_video(args: argparse.Namespace):
    """Backfill the speeches video."""
    start = dt.datetime.strptime(args.start, "%Y-%m-%d")
    end = dt.datetime.strptime(args.end, "%Y-%m-%d")
    print(f"Backfill speeches video. (start: {start}, end: {end})")
    exported_videos: list[str] = []
    for delta in range((end - start).days + 1):
        date = start + dt.timedelta(days=delta)
        print(f"Backfilling speeches video at {date}")
        videos = _get_speech_video_at_date(date)
        print(f"Found {len(videos)} videos.")
        for video in videos:
            print(f"Exporting {video.url}: {video.document_id}")
            try:
                ly_parser.export_video_to_gcs(video, extract_audio=True)
            except Exception as e:  # pylint: disable=broad-except
                print(f"Error: {e}")
                continue
            exported_videos.append(video.document_id)
    if args.export:
        with open("exported_videos.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(exported_videos))


def _get_speech_video_at_date(date: dt.datetime) -> list[models.Video]:
    meetings = ly_parser.get_meetings_at_date(date)
    videos: list[readers.VideoEntry] = []
    for meet in meetings:
        print(f"Reading meeting: {meet.get_url()}")
        meet_reader = readers.LegislativeMeetingReader.open(meet.get_url())
        ivod_readers = [
            readers.IvodReader.open(entry.url) for entry in meet_reader.get_videos()
        ]
        videos.extend(
            video
            for ivod_reader in ivod_readers
            for video in ivod_reader.get_member_speeches()
        )
    return [
        models.Video(
            url=video.url,
            hd_url=video.hd_url,
            member=video.member,
        )
        for video in videos
    ]


def main():
    """Main function."""
    firebase_admin.initialize_app(
        options={"storageBucket": params.STORAGE_BUCKET.value}
    )

    parser = argparse.ArgumentParser(description="Backfill data in the database.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Speeches segment
    speeches_segment_parser = subparsers.add_parser(
        "speeches_segment", help="Backfill the speeches segment."
    )
    speeches_segment_parser.add_argument(
        "--start",
        "-s",
        type=str,
        help="Start time to backfill. (Format: YYYY-MM-DD)",
        default=dt.datetime(2000, 1, 1, tzinfo=models.MODEL_TIMEZONE).strftime(
            "%Y-%m-%d"
        ),
    )
    speeches_segment_parser.add_argument(
        "--end",
        "-e",
        type=str,
        help="End time to backfill. (Format: YYYY-MM-DD)",
        default=dt.datetime.now(tz=models.MODEL_TIMEZONE).strftime("%Y-%m-%d"),
    )
    speeches_segment_parser.set_defaults(func=backfill_speeches_segment)

    # Search index
    search_index_parser = subparsers.add_parser(
        "search_index", help="Backfill the search index."
    )
    search_index_parser.add_argument(
        "--host", type=str, help="Host of the search engine.", required=True
    )
    search_index_parser.add_argument(
        "--api_key", type=str, help="API key of the search engine.", required=True
    )
    search_index_parser.set_defaults(func=backfill_search_index)

    # Speeches video
    speech_video_parser = subparsers.add_parser(
        "speeches_video", help="Backfill the speeches video."
    )
    speech_video_parser.add_argument(
        "--start",
        "-s",
        type=str,
        help="Start time to backfill. (Format: YYYY-MM-DD)",
        default=dt.datetime(2000, 1, 1, tzinfo=models.MODEL_TIMEZONE).strftime(
            "%Y-%m-%d"
        ),
    )
    speech_video_parser.add_argument(
        "--end",
        "-e",
        type=str,
        help="End time to backfill. (Format: YYYY-MM-DD)",
        default=dt.datetime.now(tz=models.MODEL_TIMEZONE).strftime("%Y-%m-%d"),
    )
    speech_video_parser.add_argument(
        "--export",
        help="Export the list of downloaded videos to a file.",
        action="store_true",
    )
    speech_video_parser.set_defaults(func=backfill_speeches_video)

    args = parser.parse_args()

    if args.subcommand:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
