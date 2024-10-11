import datetime as dt

import pytz


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
