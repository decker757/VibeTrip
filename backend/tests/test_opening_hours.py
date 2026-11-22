"""A stop counts as open only if it stays open for the whole visit."""

from datetime import datetime

from backend.opening_hours import closing_time, open_for

MONDAY = 1  # Google counts days from Sunday = 0; 2026-11-30 is a Monday.


def _hours(*windows):
    return {"opening_hours": {"periods": [{"open": {"day": od, "hour": oh, "minute": 0}, "close": {"day": cd, "hour": ch, "minute": 0}} for od, oh, cd, ch in windows]}}


MUSEUM = _hours((MONDAY, 10, MONDAY, 17))
SPLIT_LUNCH_DINNER = _hours((MONDAY, 11, MONDAY, 14), (MONDAY, 17, MONDAY, 22))
LATE_BAR = _hours((MONDAY, 18, MONDAY + 1, 2))


def at(clock):
    return datetime.fromisoformat(f"2026-11-30T{clock}")


def test_arriving_just_before_closing_is_not_enough_for_the_visit():
    assert open_for(MUSEUM, at("16:55"), 90) is False


def test_a_visit_that_ends_by_closing_time_fits():
    assert open_for(MUSEUM, at("15:00"), 90) is True
    assert open_for(MUSEUM, at("15:30"), 90) is True  # leaves exactly at 17:00


def test_split_hours_need_the_visit_inside_one_window():
    assert open_for(SPLIT_LUNCH_DINNER, at("13:30"), 60) is False
    assert open_for(SPLIT_LUNCH_DINNER, at("12:00"), 60) is True


def test_a_window_past_midnight_counts_until_it_closes():
    assert open_for(LATE_BAR, at("23:30"), 90) is True


def test_unknown_or_round_the_clock_hours():
    assert open_for({}, at("23:30"), 90) is None
    assert open_for({"opening_hours": {"periods": [{"open": {"day": 0, "hour": 0, "minute": 0}}]}}, at("03:00"), 90) is True


def test_closing_time_of_the_window_you_arrive_in():
    assert closing_time(MUSEUM, at("16:55")) == at("17:00")
    assert closing_time(MUSEUM, at("18:00")) is None
