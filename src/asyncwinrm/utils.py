from __future__ import annotations

from datetime import timedelta
from typing import Union

from isodate import Duration, duration_isoformat

DurationLike = Union[int, float, timedelta, Duration]


def sec_to_duration(value: DurationLike) -> str:
    if isinstance(value, (int, float)):
        value = timedelta(seconds=value)
    return duration_isoformat(value)
