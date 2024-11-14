"""Generate weekly news titles and content."""

import dataclasses
import datetime as dt
import json

import gembatch  # type: ignore
from ai import gemini, langchain
from firebase_admin import firestore  # type: ignore
from legislature import models
from vertexai import generative_models as gm  # type: ignore


@dataclasses.dataclass
class GenerateWeeklyNewsContext:
    """Context for generating weekly news."""

    report_uri: str = ""
    transcript_uri: str = ""
    start: str | dt.datetime | None = None
    end: str | dt.datetime | None = None

    def __post_init__(self):
        if isinstance(self.start, dt.datetime):
            self.start = self.start.isoformat()
        if isinstance(self.end, dt.datetime):
            self.end = self.end.isoformat()

    def get_start(self) -> dt.datetime | None:
        """Get the start date."""
        if self.start is None:
            return None
        elif isinstance(self.start, dt.datetime):
            return self.start
        else:
            return dt.datetime.fromisoformat(self.start)

    def get_end(self) -> dt.datetime | None:
        """Get the end date."""
        if self.end is None:
            return None
        elif isinstance(self.end, dt.datetime):
            return self.end
        else:
            return dt.datetime.fromisoformat(self.end)

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "GenerateWeeklyNewsContext":
        """Create from dictionary."""
        return cls(**data)


def start_generate_weekly_news(
    ctx: GenerateWeeklyNewsContext,
    content: str,
    model: str = "publishers/google/models/gemini-1.5-pro-001",
):
    """Generate weekly news titles."""
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": content},
                        {
                            "text": "請依照討論度最高的幾個議題，撰寫新聞標題。注意不要提及人名。"
                        },
                    ],
                }
            ],
            "safetySettings": gemini.NON_BLOCKING_SAFE_SETTINGS,
        },
        model,
        on_receive_weekly_news_titles,
        dict(ctx=ctx.to_dict(), model=model),
    )


def on_receive_weekly_news_titles(
    response: gm.GenerationResponse,
    ctx: dict[str, str],
    model: str = "publishers/google/models/gemini-1.5-pro-001",
):
    """Clean up the titles."""
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": response.text},
                        {"text": "整理出前文提到的新聞標題，並移除太相似的標題。"},
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
        model,
        on_receive_weekly_news_cleanup_titles,
        dict(ctx=ctx, model=model),
    )


def on_receive_weekly_news_cleanup_titles(
    response: gm.GenerationResponse,
    ctx: dict[str, str],
    model: str = "publishers/google/models/gemini-1.5-pro-001",
):
    """Generate weekly news content."""
    context = GenerateWeeklyNewsContext.from_dict(ctx)
    titles = json.loads(response.text)[0:10]
    weekly_report = models.WeeklyReport(
        report_date=context.get_end(),
        titles=titles,
        all_report_uri=context.report_uri,
        transcript_uri=context.transcript_uri,
    )
    db = firestore.client()
    db.collection(models.WEEKLY_COLLECT).document(str(weekly_report.week)).set(
        weekly_report.asdict(), merge=True
    )
    for title in titles[0:2]:  # TODO: Remove the limit
        ref = db.collection(models.NEWS_REPORT_COLLECT).document()
        report = models.NewsReport(
            title=title,
            source_uri=context.report_uri,
            transcript_uri=context.transcript_uri,
            report_date=context.get_end(),
        )
        ref.set(report.asdict())
        start_generate_weekly_news_content(ref.id, report, model=model)


def start_generate_weekly_news_content(
    doc_id: str,
    report: models.NewsReport,
    model: str = "publishers/google/models/gemini-1.5-pro-001",
):
    """Generate weekly news content."""
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"# 會議紀錄\n\n{report.get_transcript_text()}\n\n"},
                        {
                            "text": (
                                f"以 {report.title} 為標題，撰寫一篇新聞報導的內文。注意:\n"
                                "1. 使用繁體中文。\n"
                                "2. 開頭不需要日期和出處。\n"
                                "3. 不需要有標題。\n"
                            )
                        },
                    ],
                }
            ],
            "safetySettings": gemini.NON_BLOCKING_SAFE_SETTINGS,
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "object",
                    "properties": {
                        "body": {"type": "string"},
                    },
                },
            },
        },
        model,
        on_receive_weekly_news_content,
        dict(doc_id=doc_id, model=model),
    )


def on_receive_weekly_news_content(
    response: gm.GenerationResponse,
    doc_id: str = "",
    model: str = "publishers/google/models/gemini-1.5-pro-001",
):
    """Update the news report with content."""
    db = firestore.client()
    ref = db.collection(models.NEWS_REPORT_COLLECT).document(doc_id)
    doc = ref.get()
    if not doc.exists:
        raise ValueError(f"Document {doc_id} not found.")
    report = models.NewsReport.from_dict(doc.to_dict())
    data = json.loads(response.text)
    report.content = data["body"]
    report.keywords = langchain.generate_news_keywords(
        langchain.WeeklyNews(title=report.title, content=report.content or "")
    )
    ref.update(report.asdict())
    start_search_news_stakeholders(doc_id, report, model=model)


def start_search_news_stakeholders(
    doc_id: str,
    report: models.NewsReport,
    model: str = "publishers/google/models/gemini-1.5-pro-001",
):
    """Search for stakeholders in the news report."""
    gembatch.submit(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": report.get_transcript_text()},
                        {
                            "text": (
                                f"參考下篇新聞報導，找出有討論到這則報導的委員。\n"
                                f"{report.title}: {report.content}\n\n"
                            )
                        },
                    ],
                }
            ],
            "safetySettings": gemini.NON_BLOCKING_SAFE_SETTINGS,
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "立法委員姓名",
                },
            },
        },
        model,
        on_receive_weekly_news_stakeholders,
        dict(doc_id=doc_id),
    )


def on_receive_weekly_news_stakeholders(
    response: gm.GenerationResponse, doc_id: str = ""
):
    """Update the news report with stakeholders."""
    names = json.loads(response.text)
    valid_names: list[str] = []
    for name in names:
        if "###" in name or ":" in name or len(name) > 20:
            continue
        valid_names.append(name)
    db = firestore.client()
    ref = db.collection(models.NEWS_REPORT_COLLECT).document(doc_id)
    doc = ref.get()
    if not doc.exists:
        raise ValueError(f"Document {doc_id} not found.")
    report = models.NewsReport.from_dict(doc.to_dict())
    report.legislators = valid_names
    report.is_ready = True
    ref.update(report.asdict())
