"""eLicznik answers for the previous day before all its hours are available:
first with every hourly value null ("sum": 0), later with only the first hours
filled and the rest null. Such a day was taken as the daily value, so daily
sensors showed 0 or part of the day instead of the last complete day."""
import asyncio
import datetime
import types

import pytest

from custom_components.tauron_amiplus import connector as connector_module
from custom_components.tauron_amiplus.connector import TauronAmiplusConnector

NOW = datetime.datetime(2026, 11, 25, 2, 40)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    class FrozenDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(connector_module, "datetime",
                        types.SimpleNamespace(datetime=FrozenDateTime, timedelta=datetime.timedelta,
                                              date=datetime.date))

HOURS = 24


def _response(values):
    """Response of energia/api for one day ("profile": "full time")."""
    return {
        "success": True,
        "data": {
            "values": values,
            "zones": {"1": sum(v or 0 for v in values)},
            "sum": sum(v or 0 for v in values),
            "chartZones": {"1": [v is not None for v in values]},
            "zonesName": {"1": "Całodobowa"},
            "allData": [
                {
                    "EC": None if v is None else str(v),
                    "Date": "",
                    "Hour": str(i + 1),
                    "Status": None if v is None else "0",
                    "Extra": None if v is None else "N",
                    "Zone": "1",
                    "Taryfa": "G11",
                }
                for i, v in enumerate(values)
            ],
        },
    }


EMPTY = [None] * HOURS
PARTIAL = [0.15] * 12 + [None] * 12
FULL = [0.15] * HOURS


def _connector(days):
    """days: offset (1 = yesterday) -> hourly values returned by the API."""
    connector = TauronAmiplusConnector("user", "password", "meter")
    asked = []

    async def fake_chart_values(payload):
        day = datetime.datetime.strptime(payload["from"], "%d.%m.%Y").date()
        offset = (NOW.date() - day).days
        asked.append(offset)
        return None if days[offset] is None else _response(days[offset])

    connector.get_chart_values = fake_chart_values
    return connector, asked


def _date(offset):
    return TauronAmiplusConnector.format_date(NOW - datetime.timedelta(offset))


def test_empty_yesterday_falls_back_to_previous_day():
    connector, asked = _connector({1: EMPTY, 2: FULL})
    data, day = asyncio.run(connector.get_values_daily(False))
    assert day == _date(2)
    assert len(data["data"]["allData"]) == HOURS
    assert asked == [1, 2]


def test_full_yesterday_is_used():
    connector, asked = _connector({1: FULL, 2: FULL})
    data, day = asyncio.run(connector.get_values_daily(False))
    assert day == _date(1)
    assert len(data["data"]["allData"]) == HOURS
    assert asked == [1]


def test_zero_consumption_is_data():
    connector, asked = _connector({1: [0] * HOURS, 2: FULL})
    data, day = asyncio.run(connector.get_values_daily(False))
    assert day == _date(1)
    assert len(data["data"]["allData"]) == HOURS


def test_no_data_in_whole_range_keeps_yesterday():
    connector, asked = _connector({offset: EMPTY for offset in range(1, 8)})
    data, day = asyncio.run(connector.get_values_daily(False))
    assert day == _date(1)
    assert data["data"]["allData"] == []
    assert asked == list(range(1, 8))


def test_failed_request_falls_back_to_previous_day():
    connector, asked = _connector({1: None, 2: FULL})
    data, day = asyncio.run(connector.get_values_daily(False))
    assert day == _date(2)
    assert asked == [1, 2]


@pytest.mark.parametrize("generation", [False, True])
def test_partial_yesterday_falls_back_to_previous_day(generation):
    connector, asked = _connector({1: PARTIAL, 2: FULL})
    data, day = asyncio.run(connector.get_values_daily(generation))
    assert day == _date(2)
    assert len(data["data"]["allData"]) == HOURS
    assert asked == [1, 2]


def test_previous_complete_day_comes_from_cache():
    connector, asked = _connector({1: PARTIAL})
    connector._cache.add_value(NOW - datetime.timedelta(2), False, _response(FULL))
    data, day = asyncio.run(connector.get_values_daily(False))
    assert day == _date(2)
    assert len(data["data"]["allData"]) == HOURS
    assert asked == [1]


def test_partial_or_empty_in_whole_range_keeps_yesterday():
    days = {offset: EMPTY for offset in range(2, 8)}
    days[1] = PARTIAL
    connector, asked = _connector(days)
    data, day = asyncio.run(connector.get_values_daily(False))
    assert day == _date(1)
    assert len(data["data"]["allData"]) == 12
    assert asked == list(range(1, 8))


def test_day_with_25_hours_is_complete():
    connector, asked = _connector({1: [0.15] * 25, 2: FULL})
    data, day = asyncio.run(connector.get_values_daily(False))
    assert day == _date(1)
    assert len(data["data"]["allData"]) == 25


def test_all_requests_failed():
    connector, asked = _connector({offset: None for offset in range(1, 8)})
    data, day = asyncio.run(connector.get_values_daily(False))
    assert data is None
    assert asked == list(range(1, 8))
