"""Tests for statistics updater and incremental synchronization."""
import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.util.dt import as_utc, get_time_zone

from custom_components.tauron_amiplus.connector import (
    TauronAmiplusDataSet,
    TauronAmiplusRawData,
)
from custom_components.tauron_amiplus.const import (
    CONF_METER_ID,
    CONF_METER_NAME,
    CONF_SHOW_BALANCED,
    CONF_SHOW_GENERATION,
    CONST_BALANCED,
    CONST_CONSUMPTION,
    CONST_GENERATION,
)
from custom_components.tauron_amiplus.statistics import TauronAmiplusStatisticsUpdater


def test_get_time():
    hour_1 = {"Date": "2026-10-24", "Hour": 1}
    t1 = TauronAmiplusStatisticsUpdater.get_time(hour_1)
    assert t1.tzinfo is not None
    # 2026-10-24 00:00 CEST -> 2026-10-23 22:00 UTC
    assert t1 == datetime.datetime(2026, 10, 23, 22, 0, tzinfo=datetime.timezone.utc)

    # 25th hour (DST change, 23:00 CET -> 22:00 UTC)
    hour_25 = {"Date": "2026-10-25", "Hour": 25}
    t25 = TauronAmiplusStatisticsUpdater.get_time(hour_25)
    assert t25.tzinfo is not None
    assert t25 == datetime.datetime(2026, 10, 25, 22, 0, tzinfo=datetime.timezone.utc)

    # Transition hours on Autumn DST day:
    # Hour 3: 02:00 CEST -> 2026-10-25 00:00 UTC
    hour_3 = {"Date": "2026-10-25", "Hour": 3}
    assert TauronAmiplusStatisticsUpdater.get_time(hour_3) == datetime.datetime(
        2026, 10, 25, 0, 0, tzinfo=datetime.timezone.utc
    )

    # Hour 4: 02:00 CET (repeat hour) -> 2026-10-25 01:00 UTC
    hour_4 = {"Date": "2026-10-25", "Hour": 4}
    assert TauronAmiplusStatisticsUpdater.get_time(hour_4) == datetime.datetime(
        2026, 10, 25, 1, 0, tzinfo=datetime.timezone.utc
    )

    # Spring DST change day: 2026-03-29 (23-hour day)
    hour_spr_1 = {"Date": "2026-03-29", "Hour": 1}
    assert TauronAmiplusStatisticsUpdater.get_time(hour_spr_1) == datetime.datetime(
        2026, 3, 28, 23, 0, tzinfo=datetime.timezone.utc
    )
    hour_spr_23 = {"Date": "2026-03-29", "Hour": 23}
    assert TauronAmiplusStatisticsUpdater.get_time(hour_spr_23) == datetime.datetime(
        2026, 3, 29, 21, 0, tzinfo=datetime.timezone.utc
    )


def test_prepare_balanced_raw_data():
    # Empty cases
    assert TauronAmiplusStatisticsUpdater.prepare_balanced_raw_data({}) == ([], [])
    assert TauronAmiplusStatisticsUpdater.prepare_balanced_raw_data({CONST_CONSUMPTION: []}) == ([], [])

    raw_data = {
        CONST_CONSUMPTION: [
            {"Date": "2026-10-24", "Hour": 1, "EC": "2.5", "Zone": "1"},
            {"Date": "2026-10-24", "Hour": 2, "EC": "1.0", "Zone": "1"},
            {"Date": "2026-10-24", "Hour": 3, "EC": "0.5", "Zone": "1"},
        ],
        CONST_GENERATION: [
            {"Date": "2026-10-24", "Hour": 1, "EC": "1.0", "Zone": "1"},  # Net consumption 1.5
            {"Date": "2026-10-24", "Hour": 2, "EC": "3.0", "Zone": "1"},  # Net generation 2.0
            # Hour 3 generation missing (e.g. dropped packet) -> safely skipped, doesn't crash
        ],
    }

    b_cons, b_gen = TauronAmiplusStatisticsUpdater.prepare_balanced_raw_data(raw_data)
    assert len(b_cons) == 2
    assert len(b_gen) == 2

    # Hour 1: 2.5 - 1.0 = 1.5 consumption, 0 gen
    assert b_cons[0]["EC"] == "1.5"
    assert b_gen[0]["EC"] == "0"

    # Hour 2: 1.0 - 3.0 = -2.0 -> 0 cons, 2.0 gen
    assert b_cons[1]["EC"] == "0"
    assert b_gen[1]["EC"] == "2.0"


async def test_update_stats_incremental(mocker):
    mock_hass = MagicMock()
    mock_add_stats = mocker.patch(
        "custom_components.tauron_amiplus.statistics.async_add_external_statistics"
    )

    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, None, "123456", "Dom", show_generation=False, show_balanced=False
    )

    raw_hours = [
        {"Date": "2026-10-24", "Hour": 1, "EC": "1.0", "Zone": "1"},
        {"Date": "2026-10-24", "Hour": 2, "EC": "2.0", "Zone": "1"},
        {"Date": "2026-10-24", "Hour": 3, "EC": "3.0", "Zone": "1"},
    ]

    # Assume hours 1 and 2 are already in Recorder up to hour 2 start
    t2 = updater.get_time(raw_hours[1])
    initial_sum = 100.0

    await updater.update_stats(
        "tauron_importer:123456_consumption",
        "Tauron Dom Zużycie",
        initial_sum,
        last_stats_time=t2,
        zone_id=None,
        raw_data=raw_hours,
    )

    mock_add_stats.assert_called_once()
    metadata, stats_data = mock_add_stats.call_args[0][1], mock_add_stats.call_args[0][2]
    # Only hour 3 should be added!
    assert len(stats_data) == 1
    assert stats_data[0]["state"] == 3.0
    assert stats_data[0]["sum"] == 103.0
    assert stats_data[0]["start"] == updater.get_time(raw_hours[2])


async def test_update_stats_all_already_recorded(mocker):
    mock_hass = MagicMock()
    mock_add_stats = mocker.patch(
        "custom_components.tauron_amiplus.statistics.async_add_external_statistics"
    )

    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, None, "123456", "Dom", show_generation=False, show_balanced=False
    )

    raw_hours = [
        {"Date": "2026-10-24", "Hour": 1, "EC": "1.0", "Zone": "1"},
        {"Date": "2026-10-24", "Hour": 2, "EC": "2.0", "Zone": "1"},
    ]

    t2 = updater.get_time(raw_hours[1])
    await updater.update_stats(
        "tauron_importer:123456_consumption",
        "Tauron Dom Zużycie",
        initial_sum=50.0,
        last_stats_time=t2,
        zone_id=None,
        raw_data=raw_hours,
    )

    # When no new hours are available, async_add_external_statistics must NOT be called
    mock_add_stats.assert_not_called()


async def test_update_stats_multizone_filtering(mocker):
    mock_hass = MagicMock()
    mock_add_stats = mocker.patch(
        "custom_components.tauron_amiplus.statistics.async_add_external_statistics"
    )

    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, None, "123456", "Dom", show_generation=False, show_balanced=False
    )

    raw_hours = [
        {"Date": "2026-10-24", "Hour": 1, "EC": "1.0", "Zone": "1"},
        {"Date": "2026-10-24", "Hour": 2, "EC": "2.0", "Zone": "2"},
        {"Date": "2026-10-24", "Hour": 3, "EC": "3.0", "Zone": "1"},
    ]

    await updater.update_stats(
        "tauron_importer:123456_consumption_zone_1",
        "Tauron Dom Zużycie Szczyt",
        initial_sum=10.0,
        last_stats_time=None,
        zone_id="1",
        raw_data=raw_hours,
    )

    mock_add_stats.assert_called_once()
    stats_data = mock_add_stats.call_args[0][2]
    assert len(stats_data) == 3
    # Hour 1 (Zone 1): usage 1.0, sum 11.0
    assert stats_data[0]["state"] == 1.0
    assert stats_data[0]["sum"] == 11.0
    # Hour 2 (Zone 2): usage 0.0 for zone 1 stat, sum remains 11.0
    assert stats_data[1]["state"] == 0.0
    assert stats_data[1]["sum"] == 11.0
    # Hour 3 (Zone 1): usage 3.0, sum 14.0
    assert stats_data[2]["state"] == 3.0
    assert stats_data[2]["sum"] == 14.0


async def test_update_all_incremental_range(mocker):
    mock_hass = MagicMock()
    mock_connector = AsyncMock()
    mock_add_stats = mocker.patch(
        "custom_components.tauron_amiplus.statistics.async_add_external_statistics"
    )

    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, mock_connector, "123456", "Dom", show_generation=False, show_balanced=False
    )

    # Mock recorder returning existing statistic up to 2026-10-23 20:00 UTC (22:00 CEST)
    last_stat_time = datetime.datetime(2026, 10, 23, 20, 0, tzinfo=datetime.timezone.utc)
    mocker.patch.object(
        updater,
        "get_last_stats",
        return_value={
            "tauron_importer:123456_consumption": [
                {
                    "start": last_stat_time.timestamp(),
                    "sum": 200.0,
                    "end": (last_stat_time + datetime.timedelta(hours=1)).timestamp(),
                }
            ]
        },
    )

    # Daily data for 2026-10-23 and 2026-10-24
    mock_connector.get_raw_values_daily_for_range.return_value = {
        "data": {
            "allData": [
                {"Date": "2026-10-23", "Hour": 22, "EC": "1.0", "Zone": "1"},  # start is 20:00 UTC -> skipped
                {"Date": "2026-10-24", "Hour": 1, "EC": "2.0", "Zone": "1"},   # start is 22:00 UTC -> added!
            ]
        }
    }

    raw_data = TauronAmiplusRawData()
    raw_data.consumption = TauronAmiplusDataSet()
    raw_data.consumption.json_daily = {"data": {"zonesName": {"1": "Taryfa jednolita"}}}

    await updater.update_all(raw_data)

    # Verify that get_raw_values_daily_for_range was called starting from min_last_date - 1 day
    mock_connector.get_raw_values_daily_for_range.assert_awaited_once()
    call_args = mock_connector.get_raw_values_daily_for_range.call_args[0]
    assert call_args[0] == datetime.date(2026, 10, 22)

    # Verify that only the new hour was saved
    mock_add_stats.assert_called_once()
    stats_data = mock_add_stats.call_args[0][2]
    assert len(stats_data) == 1
    assert stats_data[0]["state"] == 2.0
    assert stats_data[0]["sum"] == 202.0


async def test_update_all_with_explicit_start_date(mocker):
    mock_hass = MagicMock()
    mock_connector = AsyncMock()
    mock_add_stats = mocker.patch(
        "custom_components.tauron_amiplus.statistics.async_add_external_statistics"
    )

    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, mock_connector, "123456", "Dom", show_generation=False, show_balanced=False
    )

    # Existing stats are at 2026-10-20
    existing_stat_time = datetime.datetime(2026, 10, 20, 10, 0, tzinfo=datetime.timezone.utc)
    mocker.patch.object(
        updater,
        "get_last_stats",
        return_value={
            "tauron_importer:123456_consumption": [
                {
                    "start": existing_stat_time.timestamp(),
                    "sum": 500.0,
                    "end": (existing_stat_time + datetime.timedelta(hours=1)).timestamp(),
                }
            ]
        },
    )

    mock_connector.get_raw_values_daily_for_range.return_value = {
        "data": {
            "allData": [
                {"Date": "2026-10-01", "Hour": 1, "EC": "5.0", "Zone": "1"},
            ]
        }
    }

    raw_data = TauronAmiplusRawData()
    raw_data.consumption = TauronAmiplusDataSet()
    raw_data.consumption.json_daily = {"data": {"zonesName": {"1": "G11"}}}

    # User re-imports from 2026-10-01 (before existing stat)
    start_date = datetime.datetime(2026, 10, 1, 0, 0, tzinfo=get_time_zone("Europe/Warsaw"))
    await updater.update_all(raw_data, start_date=start_date)

    # fetch_from should be 2026-10-01
    call_args = mock_connector.get_raw_values_daily_for_range.call_args[0]
    assert call_args[0] == datetime.date(2026, 10, 1)

    mock_add_stats.assert_called_once()
    stats_data = mock_add_stats.call_args[0][2]
    assert stats_data[0]["sum"] == 5.0  # Reset sum to 0 + 5.0


async def test_update_all_generation_and_balanced_multizone(mocker):
    mock_hass = MagicMock()
    mock_connector = AsyncMock()
    mock_add_stats = mocker.patch(
        "custom_components.tauron_amiplus.statistics.async_add_external_statistics"
    )

    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, mock_connector, "123456", "Dom", show_generation=True, show_balanced=True
    )

    # Empty stats in recorder (initial setup)
    mocker.patch.object(updater, "get_last_stats", return_value={})

    mock_connector.get_raw_values_daily_for_range.side_effect = [
        # consumption
        {
            "data": {
                "allData": [
                    {"Date": "2026-10-24", "Hour": 1, "EC": "3.0", "Zone": "1"},
                    {"Date": "2026-10-24", "Hour": 2, "EC": "1.0", "Zone": "2"},
                ]
            }
        },
        # generation
        {
            "data": {
                "allData": [
                    {"Date": "2026-10-24", "Hour": 1, "EC": "1.0", "Zone": "1"},
                    {"Date": "2026-10-24", "Hour": 2, "EC": "4.0", "Zone": "2"},
                ]
            }
        },
    ]

    raw_data = TauronAmiplusRawData()
    raw_data.consumption = TauronAmiplusDataSet()
    raw_data.consumption.json_daily = {"data": {"zonesName": {"1": "Szczyt", "2": "Pozaszczyt"}}}

    await updater.update_all(raw_data)

    # 4 base stats (consumption, generation, balanced_consumption, balanced_generation)
    # * 3 (overall, zone 1, zone 2) = 12 statistics added
    assert mock_add_stats.call_count == 12


async def test_update_all_no_consumption_data(mocker):
    mock_hass = MagicMock()
    mock_connector = AsyncMock()
    mock_add_stats = mocker.patch(
        "custom_components.tauron_amiplus.statistics.async_add_external_statistics"
    )

    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, mock_connector, "123456", "Dom", show_generation=False, show_balanced=False
    )

    # Case 1: last_data.consumption is None
    raw_data_none = TauronAmiplusRawData()
    await updater.update_all(raw_data_none)
    mock_connector.get_raw_values_daily_for_range.assert_not_called()

    # Case 2: connector returns None
    raw_data = TauronAmiplusRawData()
    raw_data.consumption = TauronAmiplusDataSet()
    mocker.patch.object(updater, "get_last_stats", return_value={})
    mock_connector.get_raw_values_daily_for_range.return_value = None

    await updater.update_all(raw_data)
    mock_add_stats.assert_not_called()


async def test_get_last_stats_date_types(mocker):
    mock_hass = MagicMock()
    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, None, "123456", "Dom", show_generation=False, show_balanced=False
    )

    # Test float timestamp
    mocker.patch.object(
        updater,
        "get_last_stats",
        return_value={"tauron_importer:test": [{"end": 1700000000.0}]},
    )
    d1 = await updater.get_last_stats_date("tauron_importer:test")
    assert d1 == datetime.datetime(2023, 11, 14, 22, 13, 20, tzinfo=datetime.timezone.utc)

    # Test naive datetime
    mocker.patch.object(
        updater,
        "get_last_stats",
        return_value={"tauron_importer:test": [{"end": datetime.datetime(2026, 10, 24, 12, 0)}]},
    )
    d2 = await updater.get_last_stats_date("tauron_importer:test")
    assert d2.tzinfo == datetime.timezone.utc

    # Test empty
    mocker.patch.object(updater, "get_last_stats", return_value={})
    assert await updater.get_last_stats_date("tauron_importer:empty") is None


def test_are_stats_up_to_date():
    assert not TauronAmiplusStatisticsUpdater.are_stats_up_to_date(None)
    now = datetime.datetime.now(datetime.timezone.utc)
    recent = now - datetime.timedelta(days=5)
    old = now - datetime.timedelta(days=40)
    assert TauronAmiplusStatisticsUpdater.are_stats_up_to_date(recent)
    assert not TauronAmiplusStatisticsUpdater.are_stats_up_to_date(old)


async def test_manually_update_entry(mocker):
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pw",
        CONF_METER_ID: "12345",
        CONF_METER_NAME: "Dom",
    }
    mock_entry.options = {
        CONF_SHOW_GENERATION: True,
        CONF_SHOW_BALANCED: True,
    }
    mock_entry.entry_id = "test_entry_id"

    mock_connector_cls = mocker.patch("custom_components.tauron_amiplus.statistics.TauronAmiplusConnector")
    mock_connector = mock_connector_cls.return_value
    mock_data = MagicMock()
    mock_connector.get_raw_data = AsyncMock(return_value=mock_data)
    mock_connector.async_save_cache = AsyncMock()

    mock_update_all = mocker.patch.object(TauronAmiplusStatisticsUpdater, "update_all", new_callable=AsyncMock)

    await TauronAmiplusStatisticsUpdater.manually_update(
        mock_hass, datetime.date(2026, 10, 1), mock_entry
    )

    mock_connector.get_raw_data.assert_awaited_once()
    mock_update_all.assert_awaited_once()
    mock_connector.async_save_cache.assert_awaited_once()


async def test_statistics_self_healing_dst_day(mocker):
    mock_hass = MagicMock()
    mock_connector = AsyncMock()
    mock_connector._cache = MagicMock()
    mock_add_stats = mocker.patch(
        "custom_components.tauron_amiplus.statistics.async_add_external_statistics"
    )

    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, mock_connector, "123456", "Dom", show_generation=False, show_balanced=False
    )

    # Last recorded stat is at 2026-10-25 22:00 UTC (hour 25)
    last_time = datetime.datetime(2026, 10, 25, 22, 0, tzinfo=datetime.timezone.utc)
    mocker.patch.object(
        updater,
        "get_last_stats",
        return_value={
            "tauron_importer:123456_consumption": [
                {
                    "start": last_time.timestamp(),
                    "sum": 112.885,
                    "end": (last_time + datetime.timedelta(hours=1)).timestamp(),
                }
            ]
        },
    )

    # In Recorder, 2026-10-25 is detected as incomplete (missing the 01:00 UTC gap)
    mocker.patch.object(updater, "find_earliest_incomplete_day", return_value=datetime.date(2026, 10, 25))

    # Baseline before 2026-10-25 (end of 2026-10-24)
    baseline_time = datetime.datetime(2026, 10, 24, 21, 0, tzinfo=datetime.timezone.utc)
    mocker.patch.object(
        updater,
        "get_stat_before",
        return_value=(100.0, baseline_time),
    )

    # Tauron returns all 25 finalized hours for 2026-10-25 (with finalized hour 2 = 0.394 and hour 3 & 4 = 0.340)
    full_25_hours = [
        {"Date": "2026-10-25", "Hour": 1, "EC": "0.338", "Zone": "1"},
        {"Date": "2026-10-25", "Hour": 2, "EC": "0.394", "Zone": "1"},
        {"Date": "2026-10-25", "Hour": 3, "EC": "0.340", "Zone": "1"},
        {"Date": "2026-10-25", "Hour": 4, "EC": "0.340", "Zone": "1"},
    ] + [
        {"Date": "2026-10-25", "Hour": h, "EC": "0.500", "Zone": "1"}
        for h in range(5, 26)
    ]
    mock_connector.get_raw_values_daily_for_range.return_value = {
        "data": {"allData": full_25_hours}
    }

    raw_data = TauronAmiplusRawData()
    raw_data.consumption = TauronAmiplusDataSet()
    raw_data.consumption.json_daily = {"data": {"zonesName": {"1": "G11"}}}

    await updater.update_all(raw_data)

    # Should detect incomplete count (24 < 25), delete cache for 2026-10-25, and rewrite all 25 hours
    mock_connector._cache.delete_day.assert_any_call(datetime.date(2026, 10, 25))
    mock_add_stats.assert_called_once()
    stats_data = mock_add_stats.call_args[0][2]
    assert len(stats_data) == 25
    # Hour 1
    assert stats_data[0]["start"] == datetime.datetime(2026, 10, 24, 22, 0, tzinfo=datetime.timezone.utc)
    assert stats_data[0]["state"] == 0.338
    assert round(stats_data[0]["sum"], 3) == 100.338
    # Hour 2 (overwritten with 0.394 instead of provisional 0.087!)
    assert stats_data[1]["start"] == datetime.datetime(2026, 10, 24, 23, 0, tzinfo=datetime.timezone.utc)
    assert stats_data[1]["state"] == 0.394
    assert round(stats_data[1]["sum"], 3) == 100.732
    # Hour 3 (02:00 CEST)
    assert stats_data[2]["start"] == datetime.datetime(2026, 10, 25, 0, 0, tzinfo=datetime.timezone.utc)
    assert stats_data[2]["state"] == 0.340
    # Hour 4 (02:00 CET - the previously missing gap!)
    assert stats_data[3]["start"] == datetime.datetime(2026, 10, 25, 1, 0, tzinfo=datetime.timezone.utc)
    assert stats_data[3]["state"] == 0.340
    # Hour 25
    assert stats_data[24]["start"] == datetime.datetime(2026, 10, 25, 22, 0, tzinfo=datetime.timezone.utc)


def test_dst_autumn_continuity_3_days():
    # 2026-10-24 (24h), 2026-10-25 (25h), 2026-10-26 (24h) = 73 continuous UTC hours
    hours = []
    for h in range(1, 25):
        hours.append({"Date": "2026-10-24", "Hour": h})
    for h in range(1, 26):
        hours.append({"Date": "2026-10-25", "Hour": h})
    for h in range(1, 25):
        hours.append({"Date": "2026-10-26", "Hour": h})

    assert len(hours) == 73
    timestamps = [TauronAmiplusStatisticsUpdater.get_time(h) for h in hours]

    # Verify every step is exactly +1 hour in UTC
    for i in range(len(timestamps) - 1):
        diff = timestamps[i + 1] - timestamps[i]
        assert diff == datetime.timedelta(hours=1), f"Discontinuity at index {i}: {timestamps[i]} -> {timestamps[i+1]}"

    # No duplicates
    assert len(set(timestamps)) == 73
    # Start: 2026-10-23 22:00 UTC (2026-10-24 00:00 CEST)
    assert timestamps[0] == datetime.datetime(2026, 10, 23, 22, 0, tzinfo=datetime.timezone.utc)
    # End: 2026-10-26 22:00 UTC (2026-10-26 23:00 CET)
    assert timestamps[-1] == datetime.datetime(2026, 10, 26, 22, 0, tzinfo=datetime.timezone.utc)


def test_dst_spring_continuity_3_days():
    # 2026-03-28 (24h), 2026-03-29 (23h), 2026-03-30 (24h) = 71 continuous UTC hours
    hours = []
    for h in range(1, 25):
        hours.append({"Date": "2026-03-28", "Hour": h})
    for h in range(1, 24):
        hours.append({"Date": "2026-03-29", "Hour": h})
    for h in range(1, 25):
        hours.append({"Date": "2026-03-30", "Hour": h})

    assert len(hours) == 71
    timestamps = [TauronAmiplusStatisticsUpdater.get_time(h) for h in hours]

    for i in range(len(timestamps) - 1):
        diff = timestamps[i + 1] - timestamps[i]
        assert diff == datetime.timedelta(hours=1), f"Discontinuity at index {i}: {timestamps[i]} -> {timestamps[i+1]}"

    assert len(set(timestamps)) == 71
    # Start: 2026-03-27 23:00 UTC (2026-03-28 00:00 CET)
    assert timestamps[0] == datetime.datetime(2026, 3, 27, 23, 0, tzinfo=datetime.timezone.utc)
    # End: 2026-03-30 21:00 UTC (2026-03-30 23:00 CEST)
    assert timestamps[-1] == datetime.datetime(2026, 3, 30, 21, 0, tzinfo=datetime.timezone.utc)


def test_dst_autumn_balanced_25_hours():
    raw_data = {
        CONST_CONSUMPTION: [
            {"Date": "2026-10-25", "Hour": h, "EC": "2.0", "Zone": "1"}
            for h in range(1, 26)
        ],
        CONST_GENERATION: [
            {"Date": "2026-10-25", "Hour": h, "EC": "1.0", "Zone": "1"}
            for h in range(1, 26)
        ],
    }
    b_cons, b_gen = TauronAmiplusStatisticsUpdater.prepare_balanced_raw_data(raw_data)
    assert len(b_cons) == 25
    assert len(b_gen) == 25
    for c, g in zip(b_cons, b_gen):
        assert c["EC"] == "1.0"
        assert g["EC"] == "0"


async def test_find_earliest_incomplete_day(mocker):
    mock_hass = MagicMock()
    mock_connector = AsyncMock()
    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, mock_connector, "123456", "Dom", show_generation=False, show_balanced=False
    )
    stat_id = "tauron_importer:123456_consumption"

    # Suppose 2026-10-24 has 24 hours, 2026-10-25 has 24 hours (incomplete, expects 25), 2026-10-26 has 24 hours
    warsaw_tz = get_time_zone("Europe/Warsaw")
    rows = []
    # 2026-10-24: 24 hours (starting 2026-10-23 22:00 UTC)
    start_24 = datetime.datetime(2026, 10, 23, 22, 0, tzinfo=datetime.timezone.utc)
    for h in range(24):
        rows.append({"start": (start_24 + datetime.timedelta(hours=h)).timestamp()})

    # 2026-10-25: only 24 hours recorded (missing the 25th / gap hour)
    start_25 = datetime.datetime(2026, 10, 24, 22, 0, tzinfo=datetime.timezone.utc)
    for h in range(24):
        rows.append({"start": (start_25 + datetime.timedelta(hours=h)).timestamp()})

    # 2026-10-26: 24 hours
    start_26 = datetime.datetime(2026, 10, 25, 23, 0, tzinfo=datetime.timezone.utc)
    for h in range(24):
        rows.append({"start": (start_26 + datetime.timedelta(hours=h)).timestamp()})

    mock_recorder = MagicMock()
    mock_recorder.async_add_executor_job = AsyncMock(return_value={stat_id: rows})
    mocker.patch("custom_components.tauron_amiplus.statistics.get_instance", return_value=mock_recorder)

    incomplete = await updater.find_earliest_incomplete_day(
        stat_id, datetime.date(2026, 10, 24), datetime.date(2026, 10, 26)
    )
    assert incomplete == datetime.date(2026, 10, 25)

    # When 2026-10-25 also has 25 hours, nothing is incomplete
    rows.append({"start": (start_25 + datetime.timedelta(hours=24)).timestamp()})
    mock_recorder.async_add_executor_job = AsyncMock(return_value={stat_id: rows})
    incomplete_none = await updater.find_earliest_incomplete_day(
        stat_id, datetime.date(2026, 10, 24), datetime.date(2026, 10, 26)
    )
    assert incomplete_none is None


async def test_find_earliest_incomplete_day_detects_decreasing_sum(mocker):
    # Simulates corrupted Recorder state: 25 rows exist, but at hour 25 sum decreases (creating negative delta)
    mock_hass = MagicMock()
    mock_connector = AsyncMock()
    updater = TauronAmiplusStatisticsUpdater(
        mock_hass, mock_connector, "123456", "Dom", show_generation=False, show_balanced=False
    )
    stat_id = "tauron_importer:123456_consumption"

    start_25 = datetime.datetime(2026, 10, 24, 22, 0, tzinfo=datetime.timezone.utc)
    rows = []
    current_sum = 100.0
    for h in range(24):
        current_sum += 0.5
        rows.append({
            "start": (start_25 + datetime.timedelta(hours=h)).timestamp(),
            "sum": current_sum,
        })
    # 25th row has a lower sum (e.g. from an unupdated earlier sync), causing a drop
    rows.append({
        "start": (start_25 + datetime.timedelta(hours=24)).timestamp(),
        "sum": current_sum - 0.307,
    })

    mock_recorder = MagicMock()
    mock_recorder.async_add_executor_job = AsyncMock(return_value={stat_id: rows})
    mocker.patch("custom_components.tauron_amiplus.statistics.get_instance", return_value=mock_recorder)

    inconsistent = await updater.find_earliest_incomplete_day(
        stat_id, datetime.date(2026, 10, 25), datetime.date(2026, 10, 26)
    )
    assert inconsistent == datetime.date(2026, 10, 25)


