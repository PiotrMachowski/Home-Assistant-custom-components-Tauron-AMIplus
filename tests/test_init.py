"""Tests for integration setup and lifecycle."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.tauron_amiplus import (
    async_reload_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.tauron_amiplus.const import (
    CONF_METER_ID,
    CONF_METER_NAME,
    CONF_TARIFF,
    DOMAIN,
)


async def test_async_setup(mocker):
    mock_hass = MagicMock()
    mock_hass.data = {}
    mock_hass.config_entries.async_entries.return_value = []

    res = await async_setup(mock_hass, {})
    assert res is True
    assert DOMAIN in mock_hass.data


async def test_async_setup_and_unload_entry(mocker):
    mock_hass = MagicMock()
    mock_hass.data = {}
    mock_entry = MagicMock()
    mock_entry.entry_id = "entry123"
    mock_entry.data = {
        "username": "user",
        "password": "pw",
        CONF_METER_ID: "12345",
        CONF_METER_NAME: "Dom",
        CONF_TARIFF: "G11",
    }
    mock_entry.options = {}

    mock_coordinator_cls = mocker.patch("custom_components.tauron_amiplus.TauronAmiplusUpdateCoordinator")
    mock_coordinator = mock_coordinator_cls.return_value
    mock_coordinator.async_request_refresh = AsyncMock()
    mock_coordinator.connector.async_save_cache = AsyncMock()

    mocker.patch("custom_components.tauron_amiplus.register_all_services")
    mock_forward = mocker.patch.object(mock_hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock)
    mock_unload = mocker.patch.object(mock_hass.config_entries, "async_unload_platforms", new_callable=AsyncMock)

    # Setup
    assert await async_setup_entry(mock_hass, mock_entry) is True
    mock_forward.assert_awaited_once()
    mock_coordinator.async_request_refresh.assert_awaited_once()

    # Unload
    assert await async_unload_entry(mock_hass, mock_entry) is True
    mock_coordinator.connector.async_save_cache.assert_awaited_once()
    mock_unload.assert_awaited_once()
