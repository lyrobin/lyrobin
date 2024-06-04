"""
This module contains the models for the Firestore database.
"""

# pylint: disable=attribute-defined-outside-init
import dataclasses
import re
from typing import TypeVar
import datetime as dt

import deepdiff

T = TypeVar("T", bound="FireStoreDocument")


def camel_to_snake(name: str) -> str:
    """
    Converts a camel case string to snake case.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


@dataclasses.dataclass
class IntField:
    """
    A field that stores an integer.
    """

    def __init__(self, *, default: int | None = None):
        self._default = default

    def __set_name__(self, _: object, name: str) -> None:
        self._name = "_" + name
        self._default_name = name

    def __get__(self, instance: object, _: type) -> int:
        if instance is None:
            return self._default
        return getattr(instance, self._name, self._default)

    def __set__(self, instance: object, value: any) -> None:
        try:
            setattr(instance, self._name, int(value))
        except TypeError as err:
            raise TypeError(
                f"{self._default_name} must be an integer, not {value}"
            ) from err


@dataclasses.dataclass
class OptionalIntField(IntField):
    """
    A field that stores an integer or None.
    """

    def __init__(self):
        super().__init__(default=None)

    def __set__(self, instance: object, value: any) -> None:
        if value is None or value == "null":
            setattr(instance, self._name, None)
            return
        super().__set__(instance, value)


class DateTimeField:
    """
    A field that stores a datetime.
    """

    def __init__(self, *, default: dt.datetime | None = None):
        self._default = default if default is not None else dt.datetime.min

    def __set_name__(self, _: object, name: str) -> None:
        self._name = "_" + name
        self._default_name = name

    def __get__(self, instance: object, _: type) -> int:
        if instance is None:
            return self._default
        return getattr(instance, self._name)

    def __set__(self, instance: object, value: str | dt.datetime | None) -> None:
        if value is None:
            setattr(instance, self._name, dt.datetime.min)
        elif isinstance(value, dt.datetime):
            setattr(instance, self._name, value)
        elif isinstance(value, str):
            setattr(
                instance,
                self._name,
                dt.datetime.strptime(value, "%Y/%m/%d %H:%M"),
            )
        else:
            raise TypeError(
                f"{self._default_name} must be a dt.datetime or str, not {value}"
            )


@dataclasses.dataclass(match_args=False)
class FireStoreDocument:
    """
    A Firestore document.
    """

    document_id: str = ""

    def __eq__(self, other: object) -> bool:
        if not other.isinstance(self):
            return False
        return not deepdiff.DeepDiff(self.asdict(), other.asdict(), ignore_order=True)

    @classmethod
    def from_dict(cls: T, data: dict) -> T:
        """
        Creates a new instance from a dictionary.
        """
        fields = {field.name for field in dataclasses.fields(cls)}
        _data = {camel_to_snake(k): v for k, v in data.items()}
        return cls(**{k: v for k, v in _data.items() if k in fields})

    def asdict(self) -> dict:
        """
        Returns a dictionary representation of the object.
        """
        return dataclasses.asdict(self)


@dataclasses.dataclass
class Meeting(FireStoreDocument):
    """
    A meeting.
    """

    term: IntField = IntField()
    session_period: IntField = IntField()
    session_times: OptionalIntField = OptionalIntField()
    meeting_times: OptionalIntField = OptionalIntField()
    meeting_no: str = ""
    meeting_date_desc: str = ""
    meeting_date_start: DateTimeField = DateTimeField()
    meeting_date_end: DateTimeField = DateTimeField()
    meeting_room: str = ""
    meeting_unit: str = ""
    joint_committee: str = ""
    meeting_name: str = ""
    meeting_content: str = ""
    co_chairman: str = ""
    attend_legislator: str = ""

    def __post_init__(self):
        self.document_id = self.meeting_no
        date, time_desc = self.meeting_date_desc.split(" ")
        y, m, d = date.split("/")
        y = str(int(y) + 1911)
        t = dt.datetime(int(y), int(m), int(d), 0, 0)
        time_range = time_desc.split("-")
        if time_range:
            sh, sm = time_range[0].split(":")
            st = dt.timedelta(hours=int(sh), minutes=int(sm))
            self.meeting_date_start = t + st
        if len(time_range) > 1 and time_range[1]:
            eh, em = time_range[1].split(":")
            if int(eh) >= 24:
                et = dt.timedelta(days=1, minutes=int(em))
            else:
                et = dt.timedelta(hours=int(eh), minutes=int(em))
            self.meeting_date_end = t + et
