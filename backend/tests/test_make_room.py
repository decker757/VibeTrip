from datetime import date, datetime

from backend.make_room import destination_deadline

ON = date(2026, 11, 20)  # a Friday; Google weekday 5


def period(open_h, close_h, day=5, close_day=None):
    return {
        "open": {"day": day, "hour": open_h, "minute": 0},
        "close": {"day": close_day if close_day is not None else day, "hour": close_h, "minute": 0},
    }


def place(*periods, category="Art Museum"):
    return {"id": "p", "name": "P", "category": category, "opening_hours": {"periods": list(periods)}}


def test_single_window_deadline_is_close_minus_visit():
    d = destination_deadline(place(period(10, 17)), ON, datetime(2026, 11, 20, 13, 40))
    assert d.deadline == datetime(2026, 11, 20, 15, 30)
    assert d.closes_at == datetime(2026, 11, 20, 17, 0)
    assert d.visit_minutes == 90


def test_food_visit_is_60_minutes():
    assert destination_deadline(place(period(10, 22), category="Food Court"), ON, None).deadline == datetime(2026, 11, 20, 21, 0)


def test_split_hours_picks_first_window_still_reachable():
    d = destination_deadline(place(period(11, 14), period(17, 22)), ON, datetime(2026, 11, 20, 15, 0))
    assert d.deadline == datetime(2026, 11, 20, 20, 30)


def test_split_hours_picks_earliest_window_when_both_reachable():
    d = destination_deadline(place(period(17, 22), period(11, 14)), ON, datetime(2026, 11, 20, 9, 0))
    assert d.deadline == datetime(2026, 11, 20, 12, 30)


def test_no_reachable_window_uses_last_window():
    d = destination_deadline(place(period(9, 13)), ON, datetime(2026, 11, 20, 15, 5))
    assert d.deadline == datetime(2026, 11, 20, 11, 30)


def test_after_midnight_close_is_capped():
    d = destination_deadline(place(period(18, 2, close_day=6)), ON, None)
    assert d.closes_at == datetime(2026, 11, 20, 23, 59)


def test_open_24_hours_has_no_deadline():
    assert destination_deadline(place({"open": {"day": 0, "hour": 0, "minute": 0}}), ON, None) is None


def test_no_periods_that_day_has_no_deadline():
    assert destination_deadline(place(period(10, 17, day=1)), ON, None) is None
    assert destination_deadline({"id": "p", "opening_hours": {}}, ON, None) is None
