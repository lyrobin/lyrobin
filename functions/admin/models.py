import dataclasses
import datetime as dt

USER_COLLECTION = "users"


@dataclasses.dataclass
class User:
    uid: str
    google_access_token: str | None = ""
    google_refresh_token: str | None = ""
    google_expiration_time: dt.datetime | None = dataclasses.field(
        default_factory=lambda: dt.datetime.min
    )
