from typing import TypedDict, NotRequired
from vertexai import generative_models as gm  # type: ignore


class VideoMetadata(TypedDict):
    startOffset: dict[str, int]
    endOffset: dict[str, int]


class FileData(TypedDict):
    mimeType: str
    fileUri: str


class InlineData(TypedDict):
    mimeType: str
    data: str | bytes


class ContentFileData(TypedDict):
    fileData: FileData


class ContentInlineData(TypedDict):
    inlineData: InlineData


class ContentText(TypedDict):
    text: str


class Content(TypedDict):
    role: str
    parts: list[ContentText | ContentFileData | ContentInlineData]
    videoMetadata: NotRequired[VideoMetadata]


class SystemInstruction(TypedDict):
    role: NotRequired[str]
    parts: list[ContentText]


class FunctionDeclaration(TypedDict):
    name: str
    description: str
    parameters: dict


class Tool(TypedDict):
    functionDeclarations: list[FunctionDeclaration]


class SafetySetting(TypedDict):
    category: str | int
    threshold: str | int


class GenerationConfig(TypedDict, total=False):
    temperature: float
    topP: float
    topK: float
    candidateCount: int
    maxOutputTokens: int
    presencePenalty: float
    frequencyPenalty: float
    stopSequences: list[str]
    responseMimeType: str
    responseSchema: dict


class GenerateContentRequest(TypedDict):
    contents: list[Content]
    systemInstruction: NotRequired[SystemInstruction]
    tools: NotRequired[list[Tool]]
    safetySettings: NotRequired[list[SafetySetting]]
    generationConfig: NotRequired[GenerationConfig]


class SafetyRating(TypedDict):
    category: str | int
    probability: str | int
    blocked: bool


class PublicationDate(TypedDict):
    year: int
    month: int
    day: int


class Citation(TypedDict):
    startIndex: int
    endIndex: int
    uri: str
    title: str
    license: str
    publicationDate: PublicationDate


class CitationMetadata(TypedDict):
    citations: NotRequired[list[Citation]]


class ResponseContent(TypedDict):
    parts: list[ContentText]


class Candidate(TypedDict):
    content: ResponseContent
    finishReason: str | int
    safetyRatings: NotRequired[list[SafetyRating]]
    citationMetadata: NotRequired[CitationMetadata]


class UsageMetadata(TypedDict, total=False):
    promptTokenCount: int
    candidatesTokenCount: int
    totalTokenCount: int


class GenerateContentResponse(TypedDict):
    candidates: list[Candidate]
    usageMetadata: NotRequired[UsageMetadata]


DEFAULT_SAFE_SETTINGS: list[SafetySetting] = [
    {
        "category": gm.SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        "threshold": gm.SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    },
    {
        "category": gm.SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        "threshold": gm.SafetySetting.HarmBlockThreshold.BLOCK_NONE,
    },
    {
        "category": gm.SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
        "threshold": gm.SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    },
    {
        "category": gm.SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        "threshold": gm.SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    },
]
