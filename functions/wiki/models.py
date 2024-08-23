import dataclasses
import uuid

import params
from google.cloud.firestore_v1.vector import Vector

DIRECTORS_COLLECTION = "directors"
EMBEDDING_SIZE = params.EMBEDDING_SIZE.value


@dataclasses.dataclass
class WikiData:

    @classmethod
    def from_dict(cls, data: dict | None):
        if data is None:
            raise ValueError("data must be a dict.")
        fields = set(f.name for f in dataclasses.fields(cls))
        return cls(**{k: v for k, v in data.items() if k in fields})

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(unsafe_hash=True)
class WikiSection(WikiData):
    level: int = 0
    line: str = ""
    index: int = 0

    def __post_init__(self):
        self.level = int(self.level)
        self.index = int(self.index)


@dataclasses.dataclass
class WikiLink(WikiData):
    title: str = ""
    exists: bool = False


@dataclasses.dataclass
class DirectorsDocument(WikiData):
    organization: str = ""
    markdown: str = ""
    embedding: list[float] = dataclasses.field(default_factory=list)

    def document_id(self) -> str:
        return uuid.uuid3(uuid.NAMESPACE_URL, self.organization).hex

    def __post_init__(self):
        if isinstance(self.embedding, Vector):
            self.embedding = list(self.embedding)

    def to_dict(self) -> dict:
        m = super().to_dict()
        m["embedding"] = Vector(self.embedding)
        return m
