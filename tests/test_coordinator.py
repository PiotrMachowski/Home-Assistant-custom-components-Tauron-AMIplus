import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.tauron_amiplus.connector import TauronAmiplusRawData
from custom_components.tauron_amiplus.coordinator import TauronAmiplusUpdateCoordinator


async def test_coordinator_update_method_with_statistics(mocker):
    mock_hass = MagicMock()
    mock_connector_cls = mocker.patch("custom_components.tauron_amiplus.coordinator.TauronAmiplusConnector")
    mock_connector = mock_connector_cls.return_value

    mock_data = TauronAmiplusRawData()
    mock_connector.get_raw_data = AsyncMock(return_value=mock_data)
    mock_connector.async_save_cache = AsyncMock()

    mock_updater_cls = mocker.patch("custom_components.tauron_amiplus.coordinator.TauronAmiplusStatisticsUpdater")
    mock_updater = mock_updater_cls.return_value
    mock_updater.update_all = AsyncMock()

    coordinator = TauronAmiplusUpdateCoordinator(
        mock_hass,
        "entry123",
        "user",
        "pass",
        "12345",
        "Dom",
        store_statistics=True,
        config_entry=MagicMock(),
    )

    data = await coordinator.update_method()
    assert data is mock_data

    mock_connector.get_raw_data.assert_awaited_once()
    mock_updater.update_all.assert_awaited_once_with(mock_data)
    mock_connector.async_save_cache.assert_awaited_once()


async def test_coordinator_update_method_without_statistics(mocker):
    mock_hass = MagicMock()
    mock_connector_cls = mocker.patch("custom_components.tauron_amiplus.coordinator.TauronAmiplusConnector")
    mock_connector = mock_connector_cls.return_value

    mock_data = TauronAmiplusRawData()
    mock_connector.get_raw_data = AsyncMock(return_value=mock_data)
    mock_connector.async_save_cache = AsyncMock()

    mock_updater_cls = mocker.patch("custom_components.tauron_amiplus.coordinator.TauronAmiplusStatisticsUpdater")

    coordinator = TauronAmiplusUpdateCoordinator(
        mock_hass,
        "entry123",
        "user",
        "pass",
        "12345",
        "Dom",
        store_statistics=False,
        config_entry=MagicMock(),
    )

    data = await coordinator.update_method()
    assert data is mock_data

    mock_connector.get_raw_data.assert_awaited_once()
    mock_updater_cls.assert_not_called()
    mock_connector.async_save_cache.assert_awaited_once()


def test_get_next_smart_poll_window():
    from homeassistant.util.dt import get_time_zone
    import datetime

    tz = get_time_zone("Europe/Warsaw")

    # 1. At 05:00 -> next is 06:30 today
    now = datetime.datetime(2026, 10, 25, 5, 0, tzinfo=tz)
    delta, next_run = TauronAmiplusUpdateCoordinator.get_next_smart_poll_window(now=now, yesterday_complete=True)
    assert next_run == datetime.datetime(2026, 10, 25, 6, 30, tzinfo=tz)
    assert delta == datetime.timedelta(hours=1, minutes=30)

    # 2. At 07:00 -> next is 14:30 today
    now = datetime.datetime(2026, 10, 25, 7, 0, tzinfo=tz)
    delta, next_run = TauronAmiplusUpdateCoordinator.get_next_smart_poll_window(now=now, yesterday_complete=True)
    assert next_run == datetime.datetime(2026, 10, 25, 14, 30, tzinfo=tz)
    assert delta == datetime.timedelta(hours=7, minutes=30)

    # 3. At 14:35 with yesterday complete -> skip 22:30, schedule tomorrow at 06:30
    now = datetime.datetime(2026, 10, 25, 14, 35, tzinfo=tz)
    delta, next_run = TauronAmiplusUpdateCoordinator.get_next_smart_poll_window(now=now, yesterday_complete=True)
    assert next_run == datetime.datetime(2026, 10, 26, 6, 30, tzinfo=tz)

    # 4. At 14:35 with yesterday INCOMPLETE -> schedule 22:30 today!
    now = datetime.datetime(2026, 10, 25, 14, 35, tzinfo=tz)
    delta, next_run = TauronAmiplusUpdateCoordinator.get_next_smart_poll_window(now=now, yesterday_complete=False)
    assert next_run == datetime.datetime(2026, 10, 25, 22, 30, tzinfo=tz)
    assert delta == datetime.timedelta(hours=7, minutes=55)

    # 5. At 22:35 (after 22:30 retry) -> schedule tomorrow at 06:30
    now = datetime.datetime(2026, 10, 25, 22, 35, tzinfo=tz)
    delta, next_run = TauronAmiplusUpdateCoordinator.get_next_smart_poll_window(now=now, yesterday_complete=False)
    assert next_run == datetime.datetime(2026, 10, 26, 6, 30, tzinfo=tz)


async def test_coordinator_update_method_sets_smart_interval(mocker):
    mock_hass = MagicMock()
    mock_connector_cls = mocker.patch("custom_components.tauron_amiplus.coordinator.TauronAmiplusConnector")
    mock_connector = mock_connector_cls.return_value
    mock_connector.get_raw_data = AsyncMock(return_value=TauronAmiplusRawData())
    mock_connector.async_save_cache = AsyncMock()
    mock_connector.is_day_cached = MagicMock(return_value=True)

    coordinator = TauronAmiplusUpdateCoordinator(
        mock_hass,
        "entry123",
        "user",
        "pass",
        "12345",
        "Dom",
        config_entry=MagicMock(),
    )

    await coordinator.update_method()
    mock_connector.is_day_cached.assert_called_once()
    assert coordinator.update_interval is not None
    assert coordinator.update_interval > datetime.timedelta(seconds=0)


async def test_coordinator_update_failure_sets_retry_interval(mocker):
    mock_hass = MagicMock()
    mock_connector_cls = mocker.patch("custom_components.tauron_amiplus.coordinator.TauronAmiplusConnector")
    mock_connector = mock_connector_cls.return_value
    mock_connector.get_raw_data = AsyncMock(side_effect=Exception("Cannot write to closing transport"))

    coordinator = TauronAmiplusUpdateCoordinator(
        mock_hass,
        "entry123",
        "user",
        "pass",
        "12345",
        "Dom",
        config_entry=MagicMock(),
    )

    with pytest.raises(Exception, match="Cannot write to closing transport"):
        await coordinator.update_method()

    # On error, update_interval should be set to 30 minutes
    assert coordinator.update_interval == datetime.timedelta(minutes=30)



