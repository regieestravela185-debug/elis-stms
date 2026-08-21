"""
Philippine holidays.

Regular holidays are fixed by law (RA 9492 etc.) and repeat the same way
every year — Maundy Thursday/Good Friday/Black Saturday are computed from
Easter Sunday, National Heroes Day is the last Monday of August.

Special (non-working) days are NOT fixed by law — they're proclaimed by
Malacañang for each specific year and can shift. The list below is a
best-effort set for 2026 based on the usual recurring pattern (Chinese New
Year, EDSA anniversary, Ninoy Aquino Day, All Saints'/Souls', Immaculate
Conception, Christmas Eve, Last Day of the Year). Verify against the
official proclamation before relying on it, and add a new year's list here
when one becomes available — this does not auto-update.
"""
from __future__ import annotations

from datetime import date, timedelta

from dateutil.easter import easter


def _last_monday_of_august(year: int) -> date:
    d = date(year, 8, 31)
    while d.weekday() != 0:  # Monday == 0
        d -= timedelta(days=1)
    return d


def regular_holidays(year: int) -> list[dict]:
    e = easter(year)
    return [
        {"date": date(year, 1, 1), "name": "New Year's Day", "type": "regular"},
        {"date": e - timedelta(days=3), "name": "Maundy Thursday", "type": "regular"},
        {"date": e - timedelta(days=2), "name": "Good Friday", "type": "regular"},
        {"date": date(year, 4, 9), "name": "Araw ng Kagitingan", "type": "regular"},
        {"date": date(year, 5, 1), "name": "Labor Day", "type": "regular"},
        {"date": date(year, 6, 12), "name": "Independence Day", "type": "regular"},
        {"date": _last_monday_of_august(year), "name": "National Heroes Day", "type": "regular"},
        {"date": date(year, 11, 30), "name": "Bonifacio Day", "type": "regular"},
        {"date": date(year, 12, 25), "name": "Christmas Day", "type": "regular"},
        {"date": date(year, 12, 30), "name": "Rizal Day", "type": "regular"},
    ]


# Best-effort — see module docstring. Update per-year as proclamations are issued.
_SPECIAL_NON_WORKING = {
    2026: [
        {"date": date(2026, 2, 17), "name": "Chinese New Year"},
        {"date": date(2026, 2, 25), "name": "EDSA People Power Anniversary"},
        {"date": date(2026, 4, 4), "name": "Black Saturday"},
        {"date": date(2026, 8, 21), "name": "Ninoy Aquino Day"},
        {"date": date(2026, 11, 1), "name": "All Saints' Day"},
        {"date": date(2026, 11, 2), "name": "All Souls' Day"},
        {"date": date(2026, 12, 8), "name": "Feast of the Immaculate Conception"},
        {"date": date(2026, 12, 24), "name": "Christmas Eve"},
        {"date": date(2026, 12, 31), "name": "Last Day of the Year"},
    ],
}


def special_holidays(year: int) -> list[dict]:
    return [{**h, "type": "special"} for h in _SPECIAL_NON_WORKING.get(year, [])]


def holidays_for_year(year: int) -> list[dict]:
    return sorted(regular_holidays(year) + special_holidays(year), key=lambda h: h["date"])


def holidays_by_date(year: int) -> dict[date, list[dict]]:
    by_date: dict[date, list[dict]] = {}
    for h in holidays_for_year(year):
        by_date.setdefault(h["date"], []).append(h)
    return by_date
