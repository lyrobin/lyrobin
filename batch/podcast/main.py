import base64
import datetime as dt
import functools
import json
import os
import pathlib
import tempfile
import time
import traceback
import uuid
from typing import NamedTuple

import firebase_admin  # type: ignore
import google.auth.transport.requests  # type: ignore
import google.oauth2.credentials  # type: ignore
import googleapiclient.discovery  # type: ignore
import googleapiclient.http  # type: ignore
import moviepy  # type: ignore
import requests
import seewav  # type: ignore
from firebase_admin import credentials, storage
from moviepy.audio import fx as audiofx  # type: ignore
from moviepy.video.tools import subtitles as mpsub  # type: ignore
from vertexai import generative_models as gm  # type: ignore

# Secrets
YATING_API_KEY = os.environ.get("YATING_API_KEY", "")
YOUTUBE_CREDS = os.environ.get("YOUTUBE_CREDS", "")

cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(
    cred,
    {
        "storageBucket": os.environ.get(
            "STORAGE_ID", "taiwan-legislative-search.appspot.com"
        )
    },
)

BLOCK_NONE = [
    gm.SafetySetting(
        category=gm.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
        threshold=gm.HarmBlockThreshold.BLOCK_NONE,
    ),
    gm.SafetySetting(
        category=gm.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=gm.HarmBlockThreshold.BLOCK_NONE,
    ),
    gm.SafetySetting(
        category=gm.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=gm.HarmBlockThreshold.BLOCK_NONE,
    ),
    gm.SafetySetting(
        category=gm.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=gm.HarmBlockThreshold.BLOCK_NONE,
    ),
    gm.SafetySetting(
        category=gm.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=gm.HarmBlockThreshold.BLOCK_NONE,
    ),
]


class Utterance(NamedTuple):
    start: dt.datetime
    text: str


TITLES_PROMPT = """\
挑選三個本日立法院發生的重大事件或議題，用簡短的標題總結。注意:
1. 每個標題專注在一個事件或議題就好
"""

SHORT_TITLES_PROMPT = """\
挑選兩個本日立法院發生的重大事件或議題，用簡短的標題總結。注意:
1. 每個標題專注在一個事件或議題就好
"""

CONTENT_PROMPT = """\
總結【%s】，注意：

1. 以新聞播報的方式描述
2. 不要提及人名，用職稱，如：什麼什麼黨團立委、行政院長、經濟部長等。
3. 字數控制在 300 字左右
4. 請以口語的方式表達，這是主播用的講稿。
5. 保持客歡中立
"""

CLEANUP_PROMPT = """\
移除不必要的贅語：
1. 開頭，如：各位觀眾晚安、帶您關心、晚間新聞重點等...
2. 結語， 本台將持續追蹤、持續關注、持續報導等...

儘量保留原文的內容。
"""

TRANSCRIBE_PROMPT = """\
Generate a transcript in zh-tw with timestamps for each sentence in the following format:
MM:SS sentence
"""

TITLE = "%s | 立法院焦點新聞播報"

OPENING = """\
您現在收聽的是立院知更新聞播報，帶您了解%s的立法院重要議題。
"""

CLOSING = """\
以上新聞由立院知更製作，感謝您的收聽。
"""

LICENSE_INTRO = "Music by Aleksandr Karabanov from Pixabay"

LICENSE_OUTRO = "Music by Ivan Luzan from Pixabay"

FONT_PATH = "/tmp/ms-tw.ttf"

BACKGROUND_PATH = "/tmp/lyrobin_podcast.png"

INTRO_PATH = "/tmp/good-morning.wav"

OUTRO_PATH = "/tmp/beautiful-piano.wav"

LOGO_PATH = "/tmp/logo.png"


FONT_SIZE = 28
LICENSE_FONT_SIZE = 18
WAVE_FORM_POS = (720, 150)
SUBTITLE_POS = (600, 550)
LICENSE_POS = (600, 140)


def retry_with_backoff(
    max_attempts: int = 3,
    min_wait_seconds: int = 5,
    max_backoff_seconds: int = 600,
):

    def decorator_retry(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:  # pylint: disable=broad-except
                    traceback.print_exception(e)
                    print(e)
                    if i >= max_attempts:
                        raise e
                    time.sleep(min(min_wait_seconds ** (i + 1), max_backoff_seconds))

        return wrapper

    return decorator_retry


def cached_json_data(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        remote = kwargs.get("remote_target", None)
        if not remote:
            print("Warning: remote_target is empty.")
            return func(*args, **kwargs)
        blob = storage.bucket().blob(remote)
        if not blob.exists():
            data = func(*args, **kwargs)
            blob.upload_from_string(
                json.dumps(data, indent=2, ensure_ascii=False),
                content_type="application/json; charset=utf-8",
            )
            return data
        else:
            return json.loads(blob.download_as_string())

    return wrapper


def cached_file(content_type: str = "application/octet-stream"):

    def decorator_cached_file(func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            remote = kwargs.get("remote_target", None)
            if not remote:
                print("Warning: remote_target is empty.")
                return func(*args, **kwargs)
            blob = storage.bucket().blob(remote)
            if not blob.exists():
                data = func(*args, **kwargs)
                if not isinstance(data, pathlib.Path):
                    raise RuntimeError("The return value is not a pathlib.Path.")
                with data.open("rb") as f:
                    blob.upload_from_file(f, content_type=content_type)
                print(f"Uploaded {data.name} to {blob.name}")
                return data
            else:
                tempdir = tempfile.mkdtemp()
                tmp = pathlib.Path(tempdir).joinpath(pathlib.PurePath(remote).name)
                with tmp.open("wb") as f:
                    blob.download_to_file(f)
                return tmp

        return wrapper

    return decorator_cached_file


@retry_with_backoff()
@cached_json_data
def generate_news_titles(
    background_url: str,
    content_url: str,
    remote_target: str = "",  # pylint: disable=unused-argument
) -> list[str]:
    bucket = storage.bucket()
    _, content_path = content_url.replace("gs://", "").split("/", 1)
    content_blob = bucket.blob(content_path)
    content_size = len(
        json.dumps(json.loads(content_blob.download_as_string()), ensure_ascii=False)
    )
    if content_size < 10000:
        raise RuntimeError("Content is too short.")
    m = gm.GenerativeModel("gemini-1.5-flash-002")
    response = m.generate_content(
        [
            gm.Part.from_uri(background_url, "text/markdown"),
            gm.Part.from_uri(content_url, "text/plain"),
            TITLES_PROMPT if content_size > 100000 else SHORT_TITLES_PROMPT,
        ],
        safety_settings=BLOCK_NONE,
    )
    print("Title plan text: ", response.text)
    response = m.generate_content(
        [
            response.text,
        ],
        generation_config=gm.GenerationConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "array",
                "items": {"type": "string", "description": "議題"},
            },
        ),
    )
    return json.loads(response.text)


@retry_with_backoff()
@cached_json_data
def generate_news_content(
    title: str,
    background_url: str,
    content_url: str,
    remote_target: str = "",  # pylint: disable=unused-argument
) -> str:
    m = gm.GenerativeModel("gemini-1.5-flash-002")
    response = m.generate_content(
        [
            gm.Part.from_uri(background_url, "text/markdown"),
            gm.Part.from_uri(content_url, "text/plain"),
            CONTENT_PROMPT % title,
        ],
        safety_settings=BLOCK_NONE,
    )
    print(f"Content plan text ({title}): ", response.text)
    response = m.generate_content(
        [response.text, CLEANUP_PROMPT],
        generation_config=gm.GenerationConfig(
            response_mime_type="text/plain",
        ),
    )
    return response.text


def wrap_text(text: str, width: int = 20) -> str:
    lines = text.strip("。，、").split("\n")
    wrapped = []
    for line in lines:
        if len(line) <= width:
            wrapped.append(line)
            continue
        parts = [line[i : i + width] for i in range(0, len(line), width)]
        wrapped.extend(parts)
    return "\n".join(wrapped)


def timestamp_to_srt_format(text: str, duration: int = 0) -> str:
    lines = text.split("\n")
    parts = [line.split(" ") for line in lines if line]  # timestamp, txt
    utterances = [
        Utterance(dt.datetime.strptime(part[0], "%M:%S"), part[1]) for part in parts
    ]
    srt = []
    for i, u in enumerate(utterances[0:-1]):
        ts, txt = u
        next_ts, _ = utterances[i + 1]
        srt.append(
            f"{i+1}\n{ts.strftime('%H:%M:%S,000')} --> "
            f"{next_ts.strftime('%H:%M:%S,000')}\n{wrap_text(txt)}\n"
        )
    end_ts = utterances[0][0] + dt.timedelta(seconds=duration)
    srt.append(
        f"{len(utterances)}\n{utterances[-1][0].strftime('%H:%M:%S,000')} --> "
        f"{end_ts.strftime('%H:%M:%S,000')}\n{wrap_text(utterances[-1][1])}\n"
    )
    srt.append(f"{len(utterances)+1}\n")
    return "\n".join(srt)


@retry_with_backoff()
def _audio_synthesis(text) -> pathlib.Path:
    print("Audio synthesis: ", len(text))
    response = requests.post(
        "https://tts.api.yating.tw/v3/speeches/synchronize",
        headers={
            "key": YATING_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "input": {
                "text": text,
                "type": "text",
            },
            "voice": {"model": "female_1", "lang": "zh_tw"},
            "audioConfig": {
                "encoding": "LINEAR16",
                "maxLength": 2 * 60 * 1000,  # 2 minutes
                "uploadFile": False,
            },
        },
        timeout=60 * 10,  # 10 minutes
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data["audioFile"], str):
        raise RuntimeError("Audio synthesis failed with: ", data)
    audio_data = data["audioFile"]["audioContent"]
    output_dir = pathlib.Path(tempfile.mkdtemp())
    output_wav = output_dir.joinpath("audio.wav")
    with output_wav.open("wb") as f:
        f.write(base64.b64decode(audio_data))
    return output_wav


@cached_file(content_type="audio/wav")
def audio_synthesis(
    text: str,
    remote_target: str = "",  # pylint: disable=unused-argument
) -> pathlib.Path:
    output_dir = pathlib.Path(tempfile.mkdtemp())
    lines = [line for line in text.split("\n") if line]
    buffer = ""
    audios = []
    for line in lines:
        if len(buffer + line) < 300:
            buffer += line
            continue
        audios.append(_audio_synthesis(buffer))
        buffer = line
    if buffer:
        audios.append(_audio_synthesis(buffer))

    uid: str
    if remote_target:
        uid = pathlib.PurePath(remote_target).stem
    else:
        uid = uuid.uuid4().hex
    output_wav = output_dir.joinpath(f"{uid}.wav")
    clip: moviepy.AudioClip = moviepy.concatenate_audioclips(
        [moviepy.AudioFileClip(audio) for audio in audios]
    )
    clip.write_audiofile(output_wav)
    return output_wav


@retry_with_backoff()
@cached_file()
def generate_audio_srt(
    audio: pathlib.Path,
    gcs_folder: str,
    remote_target: str = "",  # pylint: disable=unused-argument
) -> pathlib.Path:
    output_dir = pathlib.Path(tempfile.mkdtemp())
    bucket = storage.bucket()
    blob = bucket.blob(f"{gcs_folder}/{audio.name}")
    if not blob.exists():
        with audio.open("rb") as f:
            blob.upload_from_file(f, content_type="audio/wav")
    else:
        print(f"Warning: audio file {audio.name} already exists.")
    gs_url = f"gs://{bucket.name}/{blob.name}"
    m = gm.GenerativeModel(model_name="gemini-1.5-flash-002")
    response = m.generate_content(
        [
            gm.Part.from_uri(gs_url, "audio/wav"),
            TRANSCRIBE_PROMPT,
        ],
        safety_settings=BLOCK_NONE,
        generation_config=gm.GenerationConfig(audio_timestamp=True),
    )
    print("SRT: ", response.text)
    response = m.generate_content(
        [
            response.text,
        ],
        generation_config=gm.GenerationConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "text": {"type": "string"},
                    },
                },
            },
        ),
    )
    date = json.loads(response.text)
    text = "\n".join([f"{d['start']} {d['text']}" for d in date])
    print(text)
    clip = moviepy.AudioFileClip(audio)
    srt_txt = timestamp_to_srt_format(text, duration=clip.duration)
    srt_path = output_dir.joinpath(f"{audio.stem}.srt")
    with srt_path.open("w", encoding="utf-8") as f:
        f.write(srt_txt)
    srt_blob = bucket.blob(f"{gcs_folder}/{srt_path.name}")
    srt_blob.upload_from_string(srt_txt, content_type="text/srt charset=utf-8")
    return srt_path


def generate_fake_audio_srt(
    text: str, duration: int, output_dir: pathlib.Path | None = None
) -> pathlib.Path:
    print("text: ", text)
    if output_dir is None:
        output_dir = pathlib.Path(tempfile.mkdtemp())
    if not output_dir:
        raise RuntimeError("output_dir is empty.")
    timestamp = "00:00 " + text + "\n"
    uid = uuid.uuid4().hex
    output_srt = output_dir.joinpath(f"{uid}.srt")
    with output_srt.open("w", encoding="utf-8") as f:
        f.write(timestamp_to_srt_format(timestamp, duration))
    return output_srt


def generate_waveform(
    audio: pathlib.Path, output_dir: pathlib.Path | None = None
) -> pathlib.Path:
    if output_dir is None:
        output_dir = pathlib.Path(tempfile.mkdtemp())
    if not output_dir:
        raise RuntimeError("output_dir is empty.")
    output = output_dir.joinpath(f"{audio.stem}.mp4")
    seewav.visualize(audio, output_dir, output)
    return output


def create_subtitle_clip(txt):
    return moviepy.TextClip(
        FONT_PATH,
        txt,
        font_size=FONT_SIZE,
        color="black",
        size=(600, None),
        stroke_color=None,
        method="caption",
        transparent=True,
        bg_color=None,
    )


def create_intro_clip(start: int) -> tuple[moviepy.VideoFileClip, moviepy.TextClip]:
    intro_wav = generate_waveform(pathlib.Path(INTRO_PATH))
    intro_clip = (
        moviepy.VideoFileClip(intro_wav).with_start(start).with_position(WAVE_FORM_POS)
    )
    text_clip = (
        moviepy.TextClip(
            FONT_PATH,
            LICENSE_INTRO,
            font_size=LICENSE_FONT_SIZE,
            color="black",
            size=(600, None),
            stroke_color=None,
            method="caption",
            transparent=True,
            bg_color=None,
        )
        .with_duration(intro_clip.duration)
        .with_start(start)
        .with_position(LICENSE_POS)
    )
    return intro_clip, text_clip


def create_outro_clip(start: int) -> tuple[moviepy.VideoFileClip, moviepy.TextClip]:
    outro_wav = generate_waveform(pathlib.Path(OUTRO_PATH))
    outro_clip = (
        moviepy.VideoFileClip(outro_wav).with_start(start).with_position(WAVE_FORM_POS)
    )
    text_clip = (
        moviepy.TextClip(
            FONT_PATH,
            LICENSE_OUTRO,
            font_size=LICENSE_FONT_SIZE,
            color="black",
            size=(600, None),
            stroke_color=None,
            method="caption",
            transparent=True,
            bg_color=None,
        )
        .with_duration(outro_clip.duration)
        .with_start(start)
        .with_position(LICENSE_POS)
    )
    return outro_clip, text_clip


def initialize_necessary_files():
    files = [
        FONT_PATH,
        BACKGROUND_PATH,
        INTRO_PATH,
        OUTRO_PATH,
        LOGO_PATH,
    ]
    bucket = storage.bucket()
    for file in files:
        file_path = pathlib.Path(file)
        if file_path.exists():
            continue
        blob = bucket.blob("podcast/assets/" + file_path.name)
        if not blob.exists():
            raise RuntimeError(f"File {blob.name} doesnjson't exist.")
        with file_path.open("wb") as f:
            blob.download_to_file(f)


def main():
    initialize_necessary_files()
    today = dt.datetime.strptime(os.environ.get("PODCAST_DATE"), "%Y-%m-%d")
    dated_folder = today.strftime("%Y%m%d")
    bucket = storage.bucket()
    background_blob = bucket.blob(f"podcast/{dated_folder}/background.txt")
    content_blob = bucket.blob(f"podcast/{dated_folder}/transcripts.txt")
    background_url = f"gs://{bucket.name}/{background_blob.name}"
    content_url = f"gs://{bucket.name}/{content_blob.name}"

    # Generate news titles and contents
    titles = generate_news_titles(
        background_url, content_url, remote_target=f"podcast/{dated_folder}/titles.json"
    )
    if not titles:
        raise RuntimeError("No titles generated.")
    print("titles: ", titles)

    contents = [
        generate_news_content(
            title,
            background_url,
            content_url,
            remote_target=f"podcast/{dated_folder}/{title}.json",
        )
        for title in titles
    ]

    # Generate audio clips
    opening = audio_synthesis(
        OPENING % today.strftime("%Y年%m月%d日"),
        remote_target=f"podcast/{dated_folder}/opening.wav",
    )
    print("Opening created: ", opening)
    opening_srt = generate_fake_audio_srt(
        OPENING % today.strftime("%Y年%m月%d日"),
        moviepy.AudioFileClip(opening).duration,
    )
    opening_waveform = generate_waveform(pathlib.Path(opening))

    closing = audio_synthesis(
        CLOSING, remote_target=f"podcast/{dated_folder}/closing.wav"
    )
    print("Closing created: ", closing)
    closing_srt = generate_fake_audio_srt(
        CLOSING, moviepy.AudioFileClip(closing).duration
    )
    closing_waveform = generate_waveform(pathlib.Path(closing))

    audios = [
        audio_synthesis(
            content, remote_target=f"podcast/{dated_folder}/content_audio_{i}.wav"
        )
        for i, content in enumerate(contents)
    ]
    srts = [
        generate_audio_srt(
            pathlib.Path(audio),
            f"podcast/{dated_folder}",
            remote_target=f"podcast/{dated_folder}/content_audio_{i}.srt",
        )
        for i, audio in enumerate(audios)
    ]
    waveforms = [generate_waveform(pathlib.Path(audio)) for audio in audios]

    waveforms = [opening_waveform] + waveforms
    srts = [opening_srt] + srts

    waveforms_clips = [
        moviepy.VideoFileClip(waveform).with_position(WAVE_FORM_POS)
        for waveform in waveforms
    ]
    subtitles_clips = [
        mpsub.SubtitlesClip(srt, make_textclip=create_subtitle_clip).with_position(
            SUBTITLE_POS
        )
        for srt in srts
    ]

    intro_clip, intro_text_clip = create_intro_clip(0)

    total_duration = start_seconds = max(intro_clip.duration, intro_text_clip.duration)
    pause_seconds = 1
    waveform_clip: moviepy.VideoClip
    subtitles_clip: mpsub.SubtitlesClip
    for i, (waveform_clip, subtitles_clip) in enumerate(
        zip(waveforms_clips, subtitles_clips)
    ):
        waveforms_clips[i] = waveform_clip.with_start(start_seconds)
        subtitles_clips[i] = subtitles_clip.with_start(start_seconds)
        duration = max(waveform_clip.duration, subtitles_clip.duration)
        start_seconds += duration + pause_seconds
        total_duration += duration + pause_seconds

    # Create outro clip
    outro_clip, outro_text_clip = create_outro_clip(start_seconds - pause_seconds)
    total_duration += outro_clip.duration
    closing_clip = (
        moviepy.VideoFileClip(closing_waveform)
        .with_position(WAVE_FORM_POS)
        .with_start(start_seconds + 0.5)
    )
    closing_text_clip = (
        mpsub.SubtitlesClip(closing_srt, make_textclip=create_subtitle_clip)
        .with_position(SUBTITLE_POS)
        .with_start(start_seconds + 1)
    )

    headline = moviepy.TextClip(
        FONT_PATH,
        TITLE % today.strftime("%Y/%m/%d"),
        font_size=36,
        color=(19, 28, 51),
        stroke_color=(19, 28, 51),
        stroke_width=1,
        size=(600, 40),
        method="label",
        transparent=True,
        bg_color=None,
    ).with_position((550, 50))
    logo = moviepy.ImageClip(LOGO_PATH).resized(0.8).with_position((450, 20))

    composed_clip = moviepy.CompositeVideoClip(
        [
            moviepy.ImageClip(BACKGROUND_PATH).with_duration(total_duration),
            headline.with_duration(total_duration),
            logo.with_duration(total_duration),
        ]
        + [intro_clip.with_volume_scaled(0.8), intro_text_clip]
        + waveforms_clips
        + subtitles_clips
        + [outro_clip.with_volume_scaled(0.8).with_effects([audiofx.AudioFadeIn(1)])]
        + [closing_clip, closing_text_clip, outro_text_clip],
        size=(1280, 720),
    )
    tempdir = pathlib.Path(tempfile.mkdtemp())
    composed_clip.write_videofile(f"{tempdir}/podcast.mp4", fps=30)
    composed_blob = bucket.blob(f"podcast/{dated_folder}/podcast.mp4")
    composed_blob.upload_from_filename(
        f"{tempdir}/podcast.mp4", content_type="video/mp4"
    )
    if YOUTUBE_CREDS:
        upload_to_youtube(today, f"{tempdir}/podcast.mp4")


def upload_to_youtube(today: dt.datetime, file_path: str):
    date_str = today.strftime("%Y/%m/%d")
    title = f"[立院知更] {date_str} 立法院焦點新聞"
    description = """\
@立院知更 每日立法院焦點新聞。
這個新聞是由大型語言模型自動生成，如果您有發現任何錯誤，歡迎在底下留言讓我們知道。
"""
    creds = google.oauth2.credentials.Credentials.from_authorized_user_info(
        json.loads(YOUTUBE_CREDS)
    )
    creds.refresh(google.auth.transport.requests.Request())
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    request = youtube.videos().insert(  # pylint: disable=no-member
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["立法院", "新聞"],
                "categoryId": "25",
            },
            "status": {
                "privacyStatus": "private",
            },
        },
        media_body=googleapiclient.http.MediaFileUpload(  # pylint: disable=no-member
            file_path,
            chunksize=-1,
            resumable=True,
        ),
    )
    response = request.execute()
    print("Video uploaded: ", response)


if __name__ == "__main__":
    try:
        print("Start generating podcast...")
        main()
    except Exception as e:  # pylint: disable=broad-except
        traceback.print_exception(e)
        raise e
