"""Legislature information parsers."""

from firebase_functions.params import StringParam


LEGISLATURE_MEETING_INFO_API = StringParam(
    name="LEGISLATURE_MEETING_INFO_API",
    default="https://data.ly.gov.tw/odw/ID42Action.action",
    description="Meeting info api",
)

LEGISLATURE_LEGISLATOR_INFO_API = StringParam(
    name="LEGISLATURE_LEGISLATOR_INFO_API",
    default="https://data.ly.gov.tw/odw/ID16Action.action",
    description="Legislator info api",
)

LEGISLATURE_MEETING_URL = StringParam(
    name="LEGISLATURE_MEETING_URL",
    default="https://ppg.ly.gov.tw/ppg/sittings",
    description="Meeting info url",
)

LEGISLATURE_PROCEEDING_URL = StringParam(
    name="LEGISLATURE_PROCEEDING_URL",
    default="https://ppg.ly.gov.tw/ppg/bills",
    description="Proceeding info url",
)
