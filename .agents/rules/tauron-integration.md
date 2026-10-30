---
description: Rules and guidelines for developing the Tauron AMIplus Home Assistant custom integration
globs: custom_components/tauron_amiplus/**
---

# Tauron AMIplus Development Rules

- **Rate Limiting**: TAURON blocks accounts upon frequent logins. Never decrease the default polling interval (8.5 hours) or introduce unthrottled requests.
- **Async & Non-blocking**: All network operations must use `aiohttp` via `async_create_clientsession(hass)`. Never run blocking I/O on the main event loop.
- **Home Assistant Standards**:
  - Do not pass `via_device: None` in `device_info`.
  - Reauth flows in `config_flow.py` must call `self.async_update_reload_and_abort(self._get_reauth_entry(), data=...)`.
  - In `sensor.py` and `statistics.py`, handle multi-zone lookups safely without hard KeyError assumptions.
  - Do not modify existing statistic IDs (`tauron_importer:<meter_id>_*`) to preserve users' historical Energy Dashboard data.
- **Verification**: Always run `python3 -m py_compile custom_components/tauron_amiplus/*.py` and validate JSON files before committing.
