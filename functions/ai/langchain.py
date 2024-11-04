"""Language chain AI functions.

Collection of functions for generating different pieces of AI generated content
that should be used to chain together to create a full meaningful content.
"""

import utils
import dataclasses
import json
from vertexai.generative_models import (  # type: ignore
    GenerativeModel,
    GenerationConfig,
    HarmCategory,
    HarmBlockThreshold,
)
from ai import context
from ai import embeddings
import io

NON_BLOCKING_SAFE_SETTINGS = {
    HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
}


@dataclasses.dataclass
class WeeklyNews:
    title: str
    content: str


@utils.retry(max_retries=5, backoff_in_seconds=5)
def generate_weekly_news_titles(
    content: str, gen_model: GenerativeModel = GenerativeModel("gemini-1.5-flash-002")
) -> list[str]:
    response = gen_model.generate_content(
        [
            content,
            ("請依照討論度最高的幾個議題，撰寫新聞標題。注意不要提及人名。"),
        ],
        safety_settings=NON_BLOCKING_SAFE_SETTINGS,
    )
    new_titles = response.text
    response = gen_model.generate_content(
        [new_titles, "整理出前文提到的新聞標題，並移除太相似的標題。"],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
        ),
        safety_settings=NON_BLOCKING_SAFE_SETTINGS,
    )
    return json.loads(response.text)[0:10]


@utils.retry(backoff_in_seconds=5)
def generate_weekly_news_with_title(
    content: str,
    news_title: str,
    gen_model: GenerativeModel = GenerativeModel("gemini-1.5-pro-001"),
) -> WeeklyNews:
    vectors = embeddings.get_embedding_vectors_from_text(news_title)
    ctx = io.StringIO()
    context.attach_directors_background(ctx, vectors)
    response = gen_model.generate_content(
        [
            ctx.getvalue(),
            f"# 會議紀錄\n\n{content}\n\n",
            (
                f"以 {news_title} 為標題，撰寫一篇新聞報導的內文。注意:\n"
                "1. 使用繁體中文。\n"
                "2. 開頭不需要日期和出處。\n"
                "3. 不需要有標題。\n"
            ),
        ],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "body": {"type": "string"},
                },
            },
        ),
    )
    data = json.loads(response.text)
    return WeeklyNews(news_title, data["body"])


@utils.retry(max_retries=3, backoff_in_seconds=5)
def search_news_stakeholders(
    content: str,
    news: WeeklyNews,
    gen_model: GenerativeModel = GenerativeModel("gemini-1.5-pro-001"),
) -> list[str]:
    response = gen_model.generate_content(
        [
            content,
            (
                "參考下篇新聞報導，找出有討論到這則報導的委員。\n"
                f"{news.title}: {news.content}\n\n"
            ),
        ],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "array",
                "items": {"type": "string"},
                "description": "立法委員姓名",
            },
            temperature=0.5,
        ),
    )
    names = json.loads(response.text)[0:10]
    for name in names:
        if "###" in name:
            raise ValueError(f"Unexpected name format: {name}")
        elif ":" in name:
            raise ValueError(f"Unexpected name format: {name}")
        elif len(name) > 20:
            raise ValueError(f"Unexpected name length: {name}")
    return names


@utils.retry(backoff_in_seconds=5)
def generate_news_keywords(
    news: WeeklyNews,
    gen_model: GenerativeModel = GenerativeModel("gemini-1.5-flash-001"),
) -> list[str]:
    response = gen_model.generate_content(
        [
            news.content,
            "在新聞報導中挑選出可用於搜尋的關鍵字，注意:\n",
            "1. 關鍵字要能在新聞報導中找到。\n",
            "2. 關鍵字要能代表新聞報導的主題。\n",
            "3. 關鍵字不可以是政黨、人名、政府機關，如立法院。\n",
        ],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "array",
                "items": {
                    "type": "string",
                },
            },
        ),
    )
    return json.loads(response.text)
