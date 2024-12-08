import datetime as dt
from typing import Literal

import pytz

TaiwanDateFormat = Literal[
    "SLASH",  # Ex: 110/01/01
    "CHINESE",  # Ex: 110年01月01日
]


def get_legislative_yuan_term(
    input_date: dt.datetime, timezone: str = "Asia/Taipei"
) -> int | None:
    """
    Determines the Legislative Yuan term based on a given date.

    Args:
        input_date: A datetime object representing the date to check.
        timezone: timezone string.

    Returns:
        The corresponding Legislative Yuan term as an integer.
    """

    tz = pytz.timezone(timezone)
    if input_date.tzinfo is None:
        input_date = input_date.replace(tzinfo=tz)

    # Define the start and end dates for each term (all timezone-aware)
    terms = {
        1: (
            dt.datetime(1948, 5, 8, tzinfo=tz),
            dt.datetime(1993, 1, 31, tzinfo=tz),
        ),
        2: (
            dt.datetime(1993, 2, 1, tzinfo=tz),
            dt.datetime(1996, 1, 31, tzinfo=tz),
        ),
        3: (
            dt.datetime(1996, 2, 1, tzinfo=tz),
            dt.datetime(1999, 1, 31, tzinfo=tz),
        ),
        4: (
            dt.datetime(1999, 2, 1, tzinfo=tz),
            dt.datetime(2002, 1, 31, tzinfo=tz),
        ),
        5: (
            dt.datetime(2002, 2, 1, tzinfo=tz),
            dt.datetime(2005, 1, 31, tzinfo=tz),
        ),
        6: (
            dt.datetime(2005, 2, 1, tzinfo=tz),
            dt.datetime(2008, 1, 31, tzinfo=tz),
        ),
        7: (
            dt.datetime(2008, 2, 1, tzinfo=tz),
            dt.datetime(2012, 1, 31, tzinfo=tz),
        ),
        8: (
            dt.datetime(2012, 2, 1, tzinfo=tz),
            dt.datetime(2016, 1, 31, tzinfo=tz),
        ),
        9: (
            dt.datetime(2016, 2, 1, tzinfo=tz),
            dt.datetime(2020, 1, 31, tzinfo=tz),
        ),
        10: (
            dt.datetime(2020, 2, 1, tzinfo=tz),
            dt.datetime(2024, 1, 31, tzinfo=tz),
        ),
        11: (
            dt.datetime(2024, 2, 1, tzinfo=tz),
            dt.datetime(2028, 1, 31, tzinfo=tz),
        ),
    }

    # Find the term that encompasses the input date
    for term, (start_date, end_date) in terms.items():
        if start_date <= input_date <= end_date:
            return term

    # If the date is outside any defined term, return None
    return None


def format_tw_year_date(date: dt.datetime, fmt: TaiwanDateFormat = "SLASH") -> str:
    """
    Format a date in the Taiwanese calendar year format.

    Args:
        date: A datetime object representing the date to format.

    Returns:
        The formatted date as a string.
    """
    if fmt == "SLASH":
        return f"{date.year - 1911}/{date.month:02}/{date.day:02}"
    elif fmt == "CHINESE":
        return f"{date.year - 1911}年{date.month:02}月{date.day:02}日"
    else:
        raise ValueError(f"Invalid TaiwanDateFormat: {fmt}")


def transform_tw_year_date_to_datetime(
    date: str, fmt: TaiwanDateFormat = "SLASH"
) -> dt.datetime:
    """
    Transform a date in the Taiwanese calendar year format to a datetime object.

    Args:
        date: A string representing the date to transform.
        fmt: The format of the input date string.

    Returns:
        The transformed date as a datetime object.
    """
    year: int
    month: int
    day: int
    if fmt == "SLASH":
        year, month, day = map(int, date.split("/"))
    elif fmt == "CHINESE":
        # result = dt.datetime.strptime(date, "%Y年%m月%d日")
        year_str, remain = date.split("年", 1)
        month_str, remain = remain.split("月", 1)
        day_str, _ = remain.split("日", 1)
        year = int(year_str)
        month = int(month_str)
        day = int(day_str)
    else:
        raise ValueError(f"Invalid TaiwanDateFormat: {fmt}")
    if year < 1911:
        year += 1911
    return dt.datetime(year, month, day)
