"""Show times in the timezone the property actually operates in.

Everything is STORED in UTC, which is right — it is unambiguous and does
not shift under daylight saving or a server move. But it was also
DISPLAYED in UTC, so an enquiry submitted at 10:30 PM in Calamba was
shown to the administrator as 2:31 PM, eight hours out.

ph() converts a stored value for display. It is deliberately forgiving:
a date has no time to shift and is returned untouched, and None passes
through so a template can still test it.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# The Philippines has one timezone and has not observed daylight saving
# since 1978, so a fixed offset is exact here and needs no tz database.
PH_OFFSET = timezone(timedelta(hours=8), name="PHT")


def ph(value):
    """A stored UTC datetime as Philippine local time."""
    if value is None:
        return None
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(PH_OFFSET)
    # A plain date carries no time of day, so there is nothing to shift.
    if isinstance(value, date):
        return value
    return value


def ph_now() -> datetime:
    """Now, in Philippine local time."""
    return datetime.now(PH_OFFSET)
