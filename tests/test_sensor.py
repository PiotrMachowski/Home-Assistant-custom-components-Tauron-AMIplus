"""Tests for sensor helper methods."""
import pytest
from custom_components.tauron_amiplus.sensor import TauronAmiplusSensor


def test_get_data_from_json():
    sample_json = {
        "data": {
            "sum": 12.3456,
            "zones": {"1": 5.1234, "2": 7.2222},
            "zonesName": {"1": "Szczyt", "2": "Poza szczytem"},
            "allData": [
                {"Date": "2026-10-20", "EC": "1.0", "Hour": 1, "Zone": "1"},
                {"Date": "2026-10-24", "EC": "2.0", "Hour": 24, "Zone": "2"},
            ]
        }
    }
    total, zones, data_range = TauronAmiplusSensor.get_data_from_json(sample_json)
    assert total == 12.346
    assert zones == {"Szczyt": 5.123, "Poza szczytem": 7.222}
    assert data_range == "2026-10-20 - 2026-10-24"


def test_get_balanced_data_normal():
    con_json = {
        "data": {
            "zonesName": {"1": "T1"},
            "allData": [
                {"Date": "2026-10-24", "EC": "1.5", "Hour": 1, "Zone": "1"},
                {"Date": "2026-10-24", "EC": "0.5", "Hour": 2, "Zone": "1"},
            ]
        }
    }
    gen_json = {
        "data": {
            "zonesName": {"1": "T1"},
            "allData": [
                {"Date": "2026-10-24", "EC": "0.5", "Hour": 1, "Zone": "1"},
                {"Date": "2026-10-24", "EC": "2.0", "Hour": 2, "Zone": "1"},
            ]
        }
    }
    balance, sum_con, sum_gen, zones, data_range = TauronAmiplusSensor.get_balanced_data(con_json, gen_json)
    # Hour 1: con 1.5, gen 0.5 -> diff +1.0 (consumption)
    # Hour 2: con 0.5, gen 2.0 -> diff -1.5 (generation)
    # Total balance = +1.0 + (-1.5) = -0.5
    assert sum_con == 1.0
    assert sum_gen == -1.5
    assert balance == -0.5
    assert data_range == "2026-10-24 - 2026-10-24"


def test_get_balanced_data_missing_zone_key():
    """Reproduces issue #290: KeyError when a zone id is not present in zonesName."""
    con_json = {
        "data": {
            "zonesName": {"1": "T1"},
            "allData": [
                {"Date": "2026-10-24", "EC": "1.0", "Hour": 1, "Zone": "2"},
            ]
        }
    }
    gen_json = {
        "data": {
            "zonesName": {"1": "T1"},
            "allData": [
                {"Date": "2026-10-24", "EC": "0.0", "Hour": 1, "Zone": "2"},
            ]
        }
    }
    balance, sum_con, sum_gen, zones, data_range = TauronAmiplusSensor.get_balanced_data(con_json, gen_json)
    assert balance == 1.0
    assert "zone_2_consumption" in zones
    assert zones["zone_2_consumption"] == 1.0


async def test_sensor_restore_state(mocker):
    from unittest.mock import AsyncMock, MagicMock
    from homeassistant.components.sensor import SensorStateClass
    from homeassistant.core import State

    mock_coord = MagicMock()
    mock_coord.data = None
    mock_coord.last_update_success = False
    mock_coord.async_add_listener = MagicMock(return_value=lambda: None)

    sensor = TauronAmiplusSensor(
        mock_coord,
        "Dom",
        "12345",
        "configurable_balance",
        SensorStateClass.TOTAL,
    )
    sensor.hass = MagicMock()

    # Before restore, state is None, available is False
    assert sensor.native_value is None
    assert sensor.available is False

    # Mock restored state from HA recorder/restore_state
    restored_state = State(
        "sensor.tauron_amiplus_dom_configurable_balance",
        "42.123",
        {
            "tariff": "G11",
            "sum_consumption": 100.5,
            "sum_generation": -50.2,
            "state_class": "total",
            "unit_of_measurement": "kWh",
        },
    )
    sensor.async_get_last_state = AsyncMock(return_value=restored_state)

    await sensor.async_added_to_hass()

    assert sensor.native_value == 42.123
    assert sensor.extra_state_attributes["tariff"] == "G11"
    assert sensor.extra_state_attributes["sum_consumption"] == 100.5
    assert sensor.extra_state_attributes["sum_generation"] == -50.2
    # Even though coordinator.last_update_success is False, restored state keeps entity available!
    assert sensor.available is True


async def test_sensor_restore_state_skipped_if_coord_has_data(mocker):
    from unittest.mock import AsyncMock, MagicMock
    from homeassistant.components.sensor import SensorStateClass
    from custom_components.tauron_amiplus.connector import TauronAmiplusRawData

    mock_coord = MagicMock()
    mock_coord.data = TauronAmiplusRawData()
    mock_coord.last_update_success = True
    mock_coord.async_add_listener = MagicMock(return_value=lambda: None)

    sensor = TauronAmiplusSensor(
        mock_coord,
        "Dom",
        "12345",
        "configurable_balance",
        SensorStateClass.TOTAL,
    )
    sensor.hass = MagicMock()
    sensor.async_get_last_state = AsyncMock()

    await sensor.async_added_to_hass()
    sensor.async_get_last_state.assert_not_called()
    assert sensor.available is True

