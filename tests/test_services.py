"""Tests for custom services."""
import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.tauron_amiplus.services import (
    ClearCacheService,
    DownloadStatisticsService,
    register_all_services,
)


async def test_download_statistics_service(mocker):
    mock_hass = MagicMock()
    mock_device_registry = MagicMock()
    mocker.patch(
        "custom_components.tauron_amiplus.services.dr.async_get",
        return_value=mock_device_registry,
    )
    mock_manually_update = mocker.patch(
        "custom_components.tauron_amiplus.services.TauronAmiplusStatisticsUpdater.manually_update",
        new_callable=AsyncMock,
    )

    mock_device = MagicMock()
    mock_device.config_entries = {"test_entry_id"}
    mock_device_registry.async_get.return_value = mock_device

    mock_entry = MagicMock()
    mock_hass.config_entries.async_get_entry.return_value = mock_entry

    service = DownloadStatisticsService(mock_hass)

    # Valid call (past date)
    call = MagicMock()
    past_date = datetime.date.today() - datetime.timedelta(days=5)
    call.data = {"device_id": "dev123", "start_date": past_date}

    await service.async_handle_service(call)
    mock_manually_update.assert_awaited_once_with(mock_hass, past_date, mock_entry)

    # Call with future date -> should reject and not call manually_update again
    mock_manually_update.reset_mock()
    future_date = datetime.date.today() + datetime.timedelta(days=2)
    call.data = {"device_id": "dev123", "start_date": future_date}

    await service.async_handle_service(call)
    mock_manually_update.assert_not_called()


async def test_clear_cache_service(mocker):
    mock_hass = MagicMock()
    mock_device_registry = MagicMock()
    mocker.patch(
        "custom_components.tauron_amiplus.services.dr.async_get",
        return_value=mock_device_registry,
    )

    mock_device = MagicMock()
    mock_device.config_entries = {"test_entry_id"}
    mock_device_registry.async_get.return_value = mock_device

    mock_entry = MagicMock()
    mock_connector = MagicMock()
    mock_connector.async_clear_cache = AsyncMock()
    mock_entry.runtime_data.coordinator.connector = mock_connector
    mock_hass.config_entries.async_get_entry.return_value = mock_entry

    service = ClearCacheService(mock_hass)
    call = MagicMock()
    call.data = {"device_id": "dev123"}

    await service.async_handle_service(call)
    mock_connector.async_clear_cache.assert_awaited_once()


def test_register_all_services(mocker):
    mock_hass = MagicMock()
    mock_hass.services.has_service.return_value = False

    register_all_services(mock_hass)
    assert mock_hass.services.async_register.call_count == 2

async def test_manually_update_end_to_end(mocker):
    from custom_components.tauron_amiplus.statistics import TauronAmiplusStatisticsUpdater
    from custom_components.tauron_amiplus.connector import TauronAmiplusRawData, TauronAmiplusDataSet
    from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
    from custom_components.tauron_amiplus.const import CONF_METER_ID, CONF_METER_NAME, CONF_TARIFF

    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_METER_ID: "12345",
        CONF_METER_NAME: "Dom",
        CONF_TARIFF: "G11",
    }
    mock_entry.options = {}
    mock_entry.entry_id = "entry_123"

    raw_data = TauronAmiplusRawData()
    raw_data.consumption = TauronAmiplusDataSet()
    raw_data.consumption.json_daily = {"data": {"zonesName": {"1": "G11"}}}

    mocker.patch(
        "custom_components.tauron_amiplus.connector.TauronAmiplusConnector.get_raw_data",
        new=AsyncMock(return_value=raw_data),
    )
    mocker.patch(
        "custom_components.tauron_amiplus.connector.TauronAmiplusConnector.async_save_cache",
        new=AsyncMock(),
    )
    mock_update_all = mocker.patch.object(
        TauronAmiplusStatisticsUpdater, "update_all", new=AsyncMock()
    )

    # Test with datetime.date
    await TauronAmiplusStatisticsUpdater.manually_update(
        mock_hass, datetime.date(2026, 10, 24), mock_entry
    )
    assert mock_update_all.call_count == 1

    # Test with datetime.datetime
    await TauronAmiplusStatisticsUpdater.manually_update(
        mock_hass, datetime.datetime(2026, 10, 24, 0, 0), mock_entry
    )
    assert mock_update_all.call_count == 2

