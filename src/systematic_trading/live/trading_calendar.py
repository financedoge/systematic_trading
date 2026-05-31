from __future__ import annotations

from datetime import date, timedelta


def is_us_trading_day(value: date) -> bool:
    if value.weekday() >= 5:
        return False
    return value not in us_market_holidays(value.year)


def previous_us_trading_day(value: date) -> date:
    cursor = value - timedelta(days=1)
    while not is_us_trading_day(cursor):
        cursor -= timedelta(days=1)
    return cursor


def next_us_trading_day(value: date) -> date:
    cursor = value + timedelta(days=1)
    while not is_us_trading_day(cursor):
        cursor += timedelta(days=1)
    return cursor


def us_trading_dates_after(start_date: date, end_date: date) -> list[date]:
    dates: list[date] = []
    cursor = start_date + timedelta(days=1)
    while cursor <= end_date:
        if is_us_trading_day(cursor):
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def us_market_holidays(year: int) -> set[date]:
    holidays = {
        _observed_fixed_holiday(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _good_friday(year),
        _last_weekday(year, 5, 0),
        _observed_fixed_holiday(year, 7, 4),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed_fixed_holiday(year, 12, 25),
    }
    if year >= 2022:
        holidays.add(_observed_fixed_holiday(year, 6, 19))
    return {holiday for holiday in holidays if holiday.year == year}


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    cursor = date(year, month, 1)
    while cursor.weekday() != weekday:
        cursor += timedelta(days=1)
    return cursor + timedelta(days=7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    cursor = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    return cursor


def _good_friday(year: int) -> date:
    return _easter_sunday(year) - timedelta(days=2)


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)
