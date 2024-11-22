"""This module summarizes the recent speeches of legislators."""

import datetime as dt
import json

import gembatch  # type: ignore
import utils
from ai import gemini
from firebase_admin import firestore, storage  # type: ignore
from google.cloud import firestore as gc_firestore  # type: ignore
from legislature import models, reports
from vertexai import generative_models as gm  # type: ignore


def start_summary_legislator_recent_speeches(name: str, days: int = 30, limit=200):
    """Start summarizing legislator speeches."""
    db = firestore.client()
    today = dt.datetime.now(tz=models.MODEL_TIMEZONE)
    from_date = today - dt.timedelta(days=days)
    docs = (
        db.collection_group(models.SPEECH_COLLECT)
        .where(filter=gc_firestore.FieldFilter("member", "==", name))
        .where(filter=gc_firestore.FieldFilter("start_time", ">=", from_date))
        .order_by("start_time", gc_firestore.Query.ASCENDING)
        .limit(limit)
        .stream()
    )
    speeches = [models.SpeechModel(doc.reference) for doc in docs]
    if not speeches:
        return

    bucket = storage.bucket(name=gemini.GEMINI_BUCKET)
    blob = bucket.blob(
        f"legislators/{name}/recent_speeches_summary_{today.strftime("%Y%m%d")}.txt"
    )
    blob.upload_from_string(
        reports.dump_speeches(speeches), content_type="text/plain; charset=utf-8"
    )

    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "fileData": {
                                "fileUri": utils.to_gsutil_uri(blob),
                                "mimeType": "text/plain",
                            }
                        },
                        {
                            "text": """\
以條列的方式總結委員近期的發言，注意:
1. 只需要標題。
2. 儘可能的將多個發言內容歸納成一個主題。
3. 數量控制在 10 個左右
4. 避免冗言贅語，直接表達主題即可。 例如: "立法院委員會質詢：...", "立法院公聽會：..." 都不需要。
5. 不要使用姓名開頭，例如: "王委員質詢：..." 可以直接省略。

合併議題的方式可參考:
1. "灰色地帶策略下的國安危機：中國對台灣港口的滲透" , "數發部預算執行成效檢討：高齡科技及數位前瞻計畫": "政府預算使用效能與國家安全"
2. "交通部虛擬觀光計畫成效檢討與臺鐵屏佳道遮斷器安全問題", "馬自達召回事件處理及T3航廈標案爭議": "交通部施政檢討：計畫成效、廠商管理與消費者權益"
"""
                        },
                    ],
                }
            ],
            "safetySettings": gemini.NON_BLOCKING_SAFE_SETTINGS,
        },
        "publishers/google/models/gemini-1.5-flash-002",
        on_receive_recent_speeches_topics,
        {
            "uri": utils.to_gsutil_uri(blob),
            "member": name,
        },
    )


def on_receive_recent_speeches_topics(
    response: gm.GenerationResponse, uri: str, member: str = ""
):
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": response.text,
                        },
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "safetySettings": gemini.NON_BLOCKING_SAFE_SETTINGS,
        },
        "publishers/google/models/gemini-1.5-flash-002",
        on_receive_recent_speeches_cleaned_topics,
        {
            "uri": uri,
            "member": member,
        },
    )


def on_receive_recent_speeches_cleaned_topics(
    response: gm.GenerationResponse, uri: str = "", member: str = ""
):
    if not uri or not member:
        raise ValueError("Missing required parameters")
    if not response.text:
        raise ValueError("No response text")

    db = firestore.client()
    candidates = (
        db.collection(models.MEMBER_COLLECT).where("name", "==", member).limit(1).get()
    )
    if len(candidates) <= 0 or not candidates[0].exists:
        raise ValueError(f"Legislator {member} not found.")
    m = models.LegislatorModel(candidates[0].reference)

    titles = list(set(json.loads(response.text)))
    summary = m.add_summary(
        models.LegislatorSummary(
            topics=titles,
            context_uri=uri,
            created_at=dt.datetime.now(tz=models.MODEL_TIMEZONE),
        )
    )

    for title in titles:
        start_summary_legislator_recent_speeches_by_topic(
            member=m.value, topic=title, context_uri=uri, summary_path=summary.ref.path
        )


def start_summary_legislator_recent_speeches_by_topic(
    member: models.Legislator, topic: str, context_uri: str, summary_path: str
):
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "fileData": {
                                "fileUri": context_uri,
                                "mimeType": "text/plain",
                            }
                        },
                        {
                            "text": (
                                f"總結和 ⌈{topic}⌋ 相關的發言。注意：\n"
                                f"1. 質詢的委員是{member.party}的{member.name}委員。\n"
                                "2. 不要用姓名來稱戶官員，改用職稱取代。如：行政院長、經濟部長。\n"
                                "3. 不需要重覆標題。\n"
                                "4. 使用條列的方式呈現\n"
                            ),
                        },
                    ],
                }
            ],
            "safetySettings": gemini.NON_BLOCKING_SAFE_SETTINGS,
        },
        "publishers/google/models/gemini-1.5-flash-002",
        on_receive_recent_speeches_summary_by_topic,
        {
            "topic": topic,
            "summary_path": summary_path,
        },
    )


def on_receive_recent_speeches_summary_by_topic(
    response: gm.GenerationResponse, topic: str = "", summary_path: str = ""
):
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": response.text,
                        },
                        {
                            "text": (
                                "截取上文中條列的重點，注意：\n"
                                "1. 省去冗言，如 ：重點如下...\n"
                                "2. 列出多個重點\n"
                                "3. 輸出為 JSON，資料格式是有多個字串的陣列\n"
                            )
                        },
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "safetySettings": gemini.NON_BLOCKING_SAFE_SETTINGS,
        },
        "publishers/google/models/gemini-1.5-flash-002",
        on_receive_recent_speeches_cleaned_summary_by_topic,
        {"topic": topic, "summary_path": summary_path},
    )


def on_receive_recent_speeches_cleaned_summary_by_topic(
    response: gm.GenerationResponse, topic: str = "", summary_path: str = ""
):
    if not topic or not summary_path:
        raise ValueError("Missing required parameters")
    if not response.text:
        raise ValueError("No response text")
    remarks = json.loads(response.text)
    db = firestore.client()
    ref = db.document(summary_path)
    if not ref.get().exists:
        raise ValueError(f"Summary not found: {summary_path}")
    summary = models.LegislatorSummaryModel(ref)
    topic_model = summary.add_topic(
        models.LegislatorSummaryTopic(
            title=topic,
            remarks=remarks,
            created_at=dt.datetime.now(tz=models.MODEL_TIMEZONE),
        )
    )
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "fileData": {
                                "fileUri": summary.value.context_uri,
                                "mimeType": "text/plain",
                            }
                        },
                        {"text": f"列舉和 ⌈{topic}⌋ 相關發言的影片連結。"},
                    ],
                }
            ],
            "safetySettings": gemini.NON_BLOCKING_SAFE_SETTINGS,
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
        },
        "publishers/google/models/gemini-1.5-flash-002",
        on_receive_topic_videos,
        {"topic_path": topic_model.ref.path},
    )


def on_receive_topic_videos(response: gm.GenerationResponse, topic_path: str = ""):
    if not topic_path:
        raise ValueError("Missing required parameters")
    if not response.text:
        raise ValueError("No response text")
    videos = list(set(json.loads(response.text)))
    db = firestore.client()
    ref = db.document(topic_path)
    if not ref.get().exists:
        raise ValueError(f"Topic not found: {topic_path}")
    topic = models.LegislatorSummaryTopicModel(ref)
    topic.value.videos = videos
    topic.value.ready = True
    topic.save()
