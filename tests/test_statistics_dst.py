"""Hourly statistics around DST changes (Europe/Warsaw).

On the last Sunday of October the hour 02:00-03:00 happens twice. eLicznik
returns it as two entries with the same "Hour" value. Both entries used to be
mapped to the same timestamp (02:00 CEST), so they were written as two rows with
an identical "start": the recorder kept only one of them and the 02:00 CET hour
disappeared from the statistics (its energy was shown in the previous hour).
"""
import asyncio
import datetime

import pytest

from custom_components.tauron_amiplus import statistics
from custom_components.tauron_amiplus.statistics import TauronAmiplusStatisticsUpdater

UTC = datetime.timezone.utc


def _day(date, hours, value="0.1"):
    return [{"EC": value, "Date": date, "Hour": h, "Zone": "1", "Status": "0"} for h in hours]


@pytest.fixture
def written(monkeypatch):
    captured = []
    monkeypatch.setattr(statistics, "async_add_external_statistics",
                        lambda hass, metadata, data: captured.extend(data))
    return captured


def _update(raw, initial_sum=0, last_stats_time=None):
    updater = TauronAmiplusStatisticsUpdater(None, None, "123", "meter", False, False)
    asyncio.run(updater.update_stats("tauron_importer:123_consumption", "name", initial_sum, last_stats_time,
                                     None, raw))


def _starts(rows):
    return [r["start"].astimezone(UTC) for r in rows]


def test_autumn_dst_repeated_hour_is_written_as_separate_hour(written):
    # 25 entries: hours 1, 2, 3, 3, 4 ... 24 (02:00-03:00 happens twice)
    _update(_day("2026-10-25", [1, 2, 3, 3, *range(4, 25)]))
    starts = _starts(written)
    assert len(set(starts)) == 25
    assert starts[:5] == [
        datetime.datetime(2026, 10, 24, 22, tzinfo=UTC),  # 00:00 CEST
        datetime.datetime(2026, 10, 24, 23, tzinfo=UTC),  # 01:00 CEST
        datetime.datetime(2026, 10, 25, 0, tzinfo=UTC),   # 02:00 CEST
        datetime.datetime(2026, 10, 25, 1, tzinfo=UTC),   # 02:00 CET (repeated hour)
        datetime.datetime(2026, 10, 25, 2, tzinfo=UTC),   # 03:00 CET
    ]
    assert starts == sorted(starts)
    assert starts[-1] == datetime.datetime(2026, 10, 25, 22, tzinfo=UTC)  # 23:00 CET
    assert written[-1]["sum"] == pytest.approx(2.5)


def test_repeated_hour_is_skipped_when_already_in_statistics(written):
    # statistics already contain everything up to 02:00 CET (01:00 UTC)
    _update(_day("2026-10-25", [1, 2, 3, 3, *range(4, 25)]), initial_sum=0.4,
            last_stats_time=datetime.datetime(2026, 10, 25, 1, tzinfo=UTC))
    starts = _starts(written)
    assert starts[0] == datetime.datetime(2026, 10, 25, 2, tzinfo=UTC)
    assert len(starts) == 21


def test_spring_dst_day_without_0200_is_unchanged(written):
    _update(_day("2026-03-29", [1, 2, *range(4, 25)]))
    starts = _starts(written)
    assert len(set(starts)) == 23
    assert starts[1] == datetime.datetime(2026, 3, 29, 0, tzinfo=UTC)  # 01:00 CET
    assert starts[2] == datetime.datetime(2026, 3, 29, 1, tzinfo=UTC)  # 03:00 CEST


def test_regular_days_are_unchanged(written):
    raw = _day("2026-11-20", range(1, 25)) + _day("2026-11-21", range(1, 25))
    _update(raw)
    expected = [datetime.datetime(2026, 11, 19, 23, tzinfo=UTC) + datetime.timedelta(hours=i) for i in range(48)]
    assert _starts(written) == expected
    assert [TauronAmiplusStatisticsUpdater.get_time(r).astimezone(UTC) for r in raw] == expected


def test_same_hour_on_consecutive_days_is_not_a_repeat(written):
    _update(_day("2026-10-24", [3]) + _day("2026-10-25", [3]))
    assert _starts(written) == [
        datetime.datetime(2026, 10, 24, 0, tzinfo=UTC),
        datetime.datetime(2026, 10, 25, 0, tzinfo=UTC),
    ]


def test_nonexistent_spring_hour_is_never_moved_backwards(written):
    # 02:00 does not exist on 2026-03-29; a repeated entry must not be shifted onto 01:00 CET
    _update(_day("2026-03-29", [1, 2, 3, 3, *range(4, 25)]))
    starts = _starts(written)
    assert starts == sorted(starts)
    assert starts[1] == datetime.datetime(2026, 3, 29, 0, tzinfo=UTC)  # 01:00 CET stays the only row at 00:00 UTC
    assert starts.count(datetime.datetime(2026, 3, 29, 0, tzinfo=UTC)) == 1
