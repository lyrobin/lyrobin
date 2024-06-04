"""Legislature information parsers."""

from firebase_functions.params import StringParam


LEGISLATURE_MEETING_INFO_API = StringParam(
    name="LEGISLATURE_MEETING_INFO_API",
    default="https://data.ly.gov.tw/odw/ID42Action.action",
    description="Meeting info api",
)

LEGISLATURE_PROCEEDINGS_URL = StringParam(
    name="LEGISLATURE_PROCEEDINGS_URL",
    default="https://ppg.ly.gov.tw/ppg/sittings",
    description="Proceeding info url",
)
