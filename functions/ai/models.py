import dataclasses
import datetime as dt


TOPICS_COLLECTION = "topics"


@dataclasses.dataclass
class Topic:
    summarized: bool = False
    tags: list[str] = dataclasses.field(default_factory=list)
    timestamp: dt.datetime = dataclasses.field(default_factory=dt.datetime.now)
    title: str = ""
    summary: str = ""

    @classmethod
    def from_dict(cls, data: dict | None):
        if data is None:
            raise ValueError("data must be a dict.")
        fields = set(f.name for f in dataclasses.fields(cls))
        return cls(**{k: v for k, v in data.items() if k in fields})

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)
