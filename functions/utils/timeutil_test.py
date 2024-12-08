import datetime as dt

import pytest
from utils import timeutil


@pytest.mark.parametrize(
    "date_str, date_fmt",
    [
        ("113/01/01", "SLASH"),
        ("113年01月01日", "CHINESE"),
        ("2024/01/01", "SLASH"),
        ("2024年01月01日", "CHINESE"),
    ],
)
def test_transform_tw_year_date_to_datetime(date_str, date_fmt):
    expect = dt.datetime(2024, 1, 1)

    result = timeutil.transform_tw_year_date_to_datetime(date_str, date_fmt)

    assert result == expect


@pytest.mark.parametrize(
    ["date", "fmt", "expect"],
    [
        (dt.datetime(2024, 1, 1), "SLASH", "113/01/01"),
        (dt.datetime(2024, 1, 1), "CHINESE", "113年01月01日"),
        (dt.datetime(2024, 12, 31), "SLASH", "113/12/31"),
        (dt.datetime(2024, 12, 31), "CHINESE", "113年12月31日"),
    ],
)
def test_format_tw_year_date(date, fmt, expect):
    result = timeutil.format_tw_year_date(date, fmt)

    assert result == expect
