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


async def test_options_flow_change_configurable_date_from_01_04_to_31_08(mocker):
    """Reproduce bug when changing configurable start date from 2026-04-01 to 2026-08-31.

    In Home Assistant, finishing an OptionsFlow (returning async_create_entry) triggers
    hass.config_entries.async_update_entry(entry, options=result["data"]), which invokes
    all registered entry.update_listeners.
    Previously:
    1. TauronAmiplusOptionsFlowHandler.async_step_user manually called
       await hass.config_entries.async_reload(entry_id) BEFORE returning output (with stale options),
       causing a redundant reload with the old date (2026-04-01) followed by a second reload.
    2. async_reload_entry called async_unload_entry + async_setup_entry directly instead of
       hass.config_entries.async_reload(entry.entry_id), bypassing ConfigEntry._on_unload cleanup,
       never shutting down old coordinators, and leaking duplicate update_listeners on each change.
    """
    import datetime
    from custom_components.tauron_amiplus.config_flow import TauronAmiplusOptionsFlowHandler
    from custom_components.tauron_amiplus.const import (
        CONF_SHOW_12_MONTHS,
        CONF_SHOW_BALANCED,
        CONF_SHOW_BALANCED_YEAR,
        CONF_SHOW_CONFIGURABLE,
        CONF_SHOW_CONFIGURABLE_DATE,
        CONF_SHOW_GENERATION,
        CONF_STORE_STATISTICS,
    )

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
    mock_entry.options = {
        CONF_SHOW_GENERATION: True,
        CONF_SHOW_12_MONTHS: True,
        CONF_SHOW_BALANCED: True,
        CONF_SHOW_BALANCED_YEAR: True,
        CONF_SHOW_CONFIGURABLE: True,
        CONF_SHOW_CONFIGURABLE_DATE: "2026-04-01",
        CONF_STORE_STATISTICS: True,
    }

    update_listeners = []
    on_unload_callbacks = []

    def add_update_listener(listener):
        update_listeners.append(listener)
        return lambda: update_listeners.remove(listener)

    def async_on_unload(cb):
        on_unload_callbacks.append(cb)

    mock_entry.add_update_listener.side_effect = add_update_listener
    mock_entry.async_on_unload.side_effect = async_on_unload

    created_coordinators = []

    def make_coordinator(*args, **kwargs):
        coord = MagicMock()
        coord.show_configurable_date = kwargs.get("show_configurable_date")
        coord.async_request_refresh = AsyncMock()
        coord.connector.async_save_cache = AsyncMock()
        created_coordinators.append(coord)
        return coord

    mocker.patch(
        "custom_components.tauron_amiplus.TauronAmiplusUpdateCoordinator",
        side_effect=make_coordinator,
    )
    mocker.patch("custom_components.tauron_amiplus.register_all_services")
    mocker.patch.object(mock_hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock)
    mocker.patch.object(mock_hass.config_entries, "async_unload_platforms", new_callable=AsyncMock)

    # Simulate HA's hass.config_entries.async_reload(entry_id), which runs unload + _on_unload + setup
    async def ha_async_reload(entry_id):
        assert entry_id == mock_entry.entry_id
        await async_unload_entry(mock_hass, mock_entry)
        while on_unload_callbacks:
            cb = on_unload_callbacks.pop()
            cb()
        await async_setup_entry(mock_hass, mock_entry)
        return True

    mock_hass.config_entries.async_reload = AsyncMock(side_effect=ha_async_reload)

    # 1. Initial setup with 2026-04-01
    await async_setup_entry(mock_hass, mock_entry)
    assert len(created_coordinators) == 1
    assert created_coordinators[0].show_configurable_date == datetime.date(2026, 4, 1)
    assert len(update_listeners) == 1

    # 2. User opens OptionsFlow and changes date from 2026-04-01 to 2026-08-31
    flow = TauronAmiplusOptionsFlowHandler(mock_entry)
    flow.hass = mock_hass
    flow.handler = mock_entry.entry_id
    mocker.patch.object(type(flow), "config_entry", new_callable=mocker.PropertyMock, return_value=mock_entry)

    await flow.async_step_init()
    new_user_input = {
        CONF_SHOW_GENERATION: True,
        CONF_SHOW_12_MONTHS: True,
        CONF_SHOW_BALANCED: True,
        CONF_SHOW_BALANCED_YEAR: True,
        CONF_SHOW_CONFIGURABLE: True,
        CONF_SHOW_CONFIGURABLE_DATE: "2026-08-31",
        CONF_STORE_STATISTICS: True,
    }
    result = await flow.async_step_user(new_user_input)

    # Simulate HA OptionsFlowManager.async_finish_flow updating entry.options and firing update_listeners
    mock_entry.options = dict(result["data"])
    for listener in list(update_listeners):
        await listener(mock_hass, mock_entry)

    # Must have reloaded ONLY ONCE (for the new date 2026-08-31), NOT twice!
    assert len(created_coordinators) == 2
    assert created_coordinators[-1].show_configurable_date == datetime.date(2026, 8, 31)
    # Must NOT leak duplicate update_listeners after reload!
    assert len(update_listeners) == 1
    mock_hass.config_entries.async_reload.assert_awaited_once_with(mock_entry.entry_id)

