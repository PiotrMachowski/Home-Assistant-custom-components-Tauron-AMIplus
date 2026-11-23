"""On 29 February the "last 12 months" range used now.replace(year=now.year - 1),
which raises ValueError (there is no 29 February in the previous year) and
aborted the whole data update for that day."""
import asyncio
import datetime
import types

import pytest

from custom_components.tauron_amiplus import connector as connector_module
from custom_components.tauron_amiplus.connector import TauronAmiplusConnector

LEAP_DAY = datetime.datetime(2028, 2, 29, 10, 30)


@pytest.fixture
def frozen_now(monkeypatch):
    def freeze(now):
        class FrozenDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return now

        monkeypatch.setattr(connector_module, "datetime",
                            types.SimpleNamespace(datetime=FrozenDateTime, timedelta=datetime.timedelta,
                                                  date=datetime.date))
    return freeze


def _connector(**kwargs):
    connector = TauronAmiplusConnector("user", "password", "meter", **kwargs)
    ranges = []

    async def fake_range(day_from, day_to, generation):
        ranges.append((day_from, day_to))
        return None

    async def fake_none(*args, **kwargs):
        return None

    async def fake_daily(generation):
        return None, None

    connector.get_raw_values_daily_for_range = fake_range
    connector.get_reading = fake_none
    connector.get_values_daily = fake_daily
    connector.get_values_monthly = fake_none
    connector.get_values_yearly = fake_none
    return connector, ranges


@pytest.mark.parametrize("now, expected_start", [
    (LEAP_DAY, datetime.datetime(2027, 2, 28, 10, 30)),
    (datetime.datetime(2026, 11, 23, 8, 0), datetime.datetime(2025, 11, 23, 8, 0)),
    (datetime.datetime(2029, 3, 1, 0, 0), datetime.datetime(2028, 3, 1, 0, 0)),
])
def test_last_12_months_range_start(frozen_now, now, expected_start):
    frozen_now(now)
    connector, ranges = _connector()
    asyncio.run(connector.get_values_12_months_hourly(False))
    assert ranges == [(expected_start, now)]


def test_data_set_with_12_months_on_leap_day(frozen_now):
    frozen_now(LEAP_DAY)
    connector, ranges = _connector(show_12_months=True)
    dataset, cache_max = asyncio.run(connector.get_data_set(False))
    assert (datetime.datetime(2027, 2, 28, 10, 30), LEAP_DAY) in ranges
    assert cache_max == datetime.datetime(2027, 2, 26, 10, 30)
