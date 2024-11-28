"""This modules build a pipeline to transcribe audio files and store other information."""

from firebase_admin import firestore  # type: ignore
from legislature import models
import gembatch  # type: ignore
from vertexai import generative_models as gm  # type: ignore
import datetime as dt
from ai import context
import ai
from utils import timeutil
import io
import json

_MODEL = "publishers/google/models/gemini-1.5-flash-002"


def start_transcribe(speech: models.SpeechModel):
    if not speech.value.audios:
        raise ValueError("No audio files to transcribe.")
    elif len(speech.value.audios) > 1:
        raise ValueError("Only one audio file is allowed.")

    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "fileData": {
                                "fileUri": speech.value.audios[0],
                                "mimeType": "audio/mp3",
                            }
                        },
                        {
                            "text": """\
Generate a transcript in zh-tw with precise timestamps for each sentence. Use the following format:

MM:SS - MM:SS [TRANSCRIPT]

where MM:SS represents the start and end time of each sentence in the video. Prioritize accuracy in timestamping and ensure the transcript faithfully captures the spoken content.
""",
                        },
                    ],
                }
            ],
            "safetySettings": ai.NON_BLOCKING_SAFE_SETTINGS,
            "generationConfig": {
                "audioTimestamp": True,
            },
        },
        _MODEL,
        on_receive_audio_transcript,
        {
            "doc_path": speech.ref.path,
        },
    )


def on_receive_audio_transcript(response: gm.GenerationResponse, doc_path: str = ""):
    if not doc_path:
        raise ValueError("No document path provided.")
    if not response.text:
        raise ValueError("No transcript generated.")
    db = firestore.client()
    ref = db.document(doc_path)
    if not ref.get().exists:
        raise ValueError(f"Document {doc_path} does not exist.")

    results: list[models.SpeechSegment] = [
        models.SpeechSegment(
            start=parts[0],
            end=parts[2],
            text=parts[3].strip(" []()"),
        )
        for line in response.text.splitlines()
        if (parts := line.split(" ", 3)) and len(parts) == 4
    ]

    batch = db.batch()
    for i, seg in enumerate(results):
        batch.set(
            ref.collection(models.SPEECH_SEGMENT_COLLECT).document(str(i)), seg.asdict()
        )
    batch.commit()

    video = models.Video.from_dict(ref.get().to_dict())
    video.transcript = "\n".join([seg.text for seg in results])
    video.transcript_updated_at = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    video.has_transcript = True
    ref.update(video.asdict())

    start_summarize_transcript(models.SpeechModel(ref))
    start_generate_hashtags(models.SpeechModel(ref))


def start_summarize_transcript(speech: models.SpeechModel):
    term = timeutil.get_legislative_yuan_term(speech.value.start_time)
    if not term:
        raise ValueError("No legislative term found.")
    buf = io.StringIO()
    context.attach_legislators_background(buf, [term])
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"逐字稿中的立法委員是 {speech.value.member}。\n",
                        },
                        {"text": "請根據下述的內容，以繁體中文做出總結。"},
                        {"text": speech.value.transcript},
                    ],
                }
            ],
            "systemInstruction": {"parts": [{"text": buf.getvalue()}]},
            "safetySettings": ai.NON_BLOCKING_SAFE_SETTINGS,
        },
        _MODEL,
        on_receive_transcript_summary,
        {
            "doc_path": speech.ref.path,
        },
    )


def start_generate_hashtags(speech: models.SpeechModel):
    gembatch.submit(
        {
            "contents": [
                {"role": "user", "parts": [{"text": speech.value.transcript}]}
            ],
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Please generate a short list of hashtags "
                            "that capture the essence of the following document. "
                            "PLease notice:\n"
                            "1. The list should be as short as possible\n"
                            "2. Do not create more than 10 tags.\n"
                            "3. Create tags in zh-TW."
                        )
                    }
                ]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "safetySettings": ai.NON_BLOCKING_SAFE_SETTINGS,
        },
        _MODEL,
        on_receive_transcript_hashtags,
        {
            "doc_path": speech.ref.path,
        },
    )


def on_receive_transcript_summary(response: gm.GenerationResponse, doc_path: str = ""):
    if not doc_path:
        raise ValueError("No document path provided.")
    if not response.text:
        raise ValueError("No summary generated.")
    db = firestore.client()
    ref = db.document(doc_path)
    if not ref.get().exists:
        raise ValueError(f"Document {doc_path} does not exist.")
    video = models.Video.from_dict(ref.get().to_dict())
    video.ai_summary = response.text
    video.ai_summarized_at = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    video.ai_summarized = True
    ref.update(video.asdict())


def on_receive_transcript_hashtags(response: gm.GenerationResponse, doc_path: str = ""):
    if not doc_path:
        raise ValueError("No document path provided.")
    if not response.text:
        raise ValueError("No hashtags generated.")
    db = firestore.client()
    ref = db.document(doc_path)
    if not ref.get().exists:
        raise ValueError(f"Document {doc_path} does not exist.")
    video = models.Video.from_dict(ref.get().to_dict())
    hashtags: list[str] = json.loads(response.text)
    if not isinstance(hashtags, list):
        raise ValueError("Hashtags must be a list.")
    video.hash_tags = [tag.strip("#") for tag in hashtags]
    video.hash_tags_summarized_at = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    video.has_hash_tags = True
    ref.update(video.asdict())
