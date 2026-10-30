# Developer & AI Agent Guidelines: Tauron AMIplus

Integration: **Tauron AMIplus** (`tauron_amiplus`)  
Target Platform: **Home Assistant** (Custom Component via HACS)  
Domain: `tauron_amiplus`  
Statistics Domain: `tauron_importer`

---

## 1. Overview & Purpose

This custom component integrates TAURON eLicznik (Polish electrical utility DSO / distribution system operator) into Home Assistant. It fetches:
- Current meter consumption/generation readings.
- Daily, monthly, yearly, and last 12-month aggregations (kWh) broken down by tariff zones (e.g. T1, T2, T3 in G11, G12, G12w, G13).
- Hourly historical energy usage and generation inserted directly into Home Assistant's **Recorder / Long-Term Statistics** (`tauron_importer:...`), enabling rich visualization in the **Home Assistant Energy Dashboard**.

---

## 2. Architecture & Component Structure

```
custom_components/tauron_amiplus/
├── __init__.py           # Config entry setup, migration (v1->v2->v3), unload, platform forwarding
├── manifest.json         # HA integration manifest (domain, dependencies, version, codeowners)
├── const.py              # Constants, URLs, sensor type mappings, intervals
├── connector.py          # HTTP client for Tauron Keycloak login, session management & eLicznik API
├── coordinator.py        # DataUpdateCoordinator handling scheduled fetches & triggering statistics
├── sensor.py             # SensorEntity implementations (regular & config_flow sensors)
├── statistics.py         # Long-term external statistics generation for Home Assistant Recorder
├── config_flow.py        # UI Configuration and Options flows (supports multi-step meter selection)
├── diagnostics.py        # Integration diagnostics dump
├── services.py           # Custom HA services (tauron_amiplus.download_statistics, clear_cache)
├── services.yaml         # Service schema and descriptions for HA UI
├── typing_helpers.py     # Type aliases (TauronAmiplusConfigEntry, TauronAmiplusRuntimeData)
└── translations/         # Localization files (en.json, pl.json)
```

### Key Technical Details

1. **Authentication Flow (Keycloak / OIDC)**:
   - TAURON migrated its authentication to Keycloak.
   - `connector.py` performs a `GET` on `https://logowanie.tauron-dystrybucja.pl/login?service=https://elicznik.tauron-dystrybucja.pl`, parses the `<form id="kc-form-login" action="...">` URL, and `POST`s credentials (`username`, `password`).
   - Session cookies (`PHPSESSID`, `ASP.NET_SessionId`) are cached in Home Assistant's `.storage` using `homeassistant.helpers.storage.Store`.
   - Before attempting a full login, the connector tries to restore and validate the existing session.

2. **Strict Rate Limiting & Anti-Ban Safeguards**:
   - TAURON enforces aggressive rate-limiting ("*Przekroczono maksymalną liczbę logowań*").
   - **CRITICAL**: The component uses **Smart Polling** (target windows at **06:30** and **14:30**, with a conditional retry at **22:30** only if yesterday's full data is missing from cache).
   - **NEVER** add frequent background polling or decrease intervals without user consent. Daily readings in Tauron eLicznik only update once or twice a day anyway (usually with 1-2 days delay).

3. **API Endpoints**:
   - `CONST_URL_SELECT_METER` (`/ustaw_punkt`): Sets the active meter on the session via `site[client]`.
   - `CONST_URL_ENERGY` (`/energia/api`) or `/energia/wo/api` (business): Main endpoint returning JSON data arrays for `full time` (hourly), `month`, and `year`.
   - `CONST_URL_READINGS` (`/odczyty/api`): Fetches the raw physical counter reading.

4. **Long-Term Statistics Injection (`statistics.py`)**:
   - Injects data into HA Recorder via `async_add_external_statistics`.
   - Statistic IDs follow the convention: `tauron_importer:<meter_id>_<suffix>`.
   - Timezones: Tauron readings are timestamped locally in Poland. All hourly timestamps are converted using the `Europe/Warsaw` timezone (`get_time_zone("Europe/Warsaw")`).

---

## 3. Development Guidelines & Conventions

### Coding Standards
- Python 3.13+ / 3.14+ syntax (use type hints, `type` aliases, dataclasses where appropriate).
- Strict adherence to Home Assistant developer guidelines:
  - Do NOT make blocking HTTP calls in the event loop (use `aiohttp` via `async_create_clientsession(hass)`).
  - Use `ConfigEntryAuthFailed` on invalid credentials to trigger HA's reauth flow.
  - Follow CoordinatorEntity patterns (`_handle_coordinator_update`).
  - Keep entities uniquely identifiable using `unique_id`.

### Verification Steps
Whenever modifying code:
1. Run syntax verification:
   ```bash
   python3 -m py_compile custom_components/tauron_amiplus/*.py
   ```
2. Validate JSON files (translations, manifest, hacs):
   ```bash
   python3 -m json.tool custom_components/tauron_amiplus/manifest.json > /dev/null
   python3 -m json.tool custom_components/tauron_amiplus/translations/pl.json > /dev/null
   python3 -m json.tool custom_components/tauron_amiplus/translations/en.json > /dev/null
   ```

---

## 4. Known Gotchas & Historical Quirks

1. **`via_device` parameter**:
   - In Home Assistant 2026.9+, passing `via_device: None` in `device_info` raises `RuntimeError`. Do not set `via_device` unless linking to another existing device.
2. **Reauth Flow (`config_flow.py`)**:
   - Reauth flows must update the existing config entry using `self.async_update_reload_and_abort(self._get_reauth_entry(), data=...)` rather than calling `async_create_entry`.
3. **Multi-zone tariff KeyError (`sensor.py` / `get_balanced_data`)**:
   - Daily responses from Tauron may contain hourly records with a `Zone` identifier that was not present in that day's `zonesName` map. Always use safe lookups (e.g. `zone_names.get(z, f"zone_{z}")`) to avoid breaking the coordinator update.
4. **Statistics ID stability**:
   - The statistic ID format (`tauron_importer:...`) is used by users' existing Energy Dashboards. Modifying this format will orphan historical statistics in HA.

---

## 5. Taking Over / Maintenance Roadmap Context

The upstream repository (`PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus`) is inactive. Active maintenance and future features (such as reactive energy sensors, net-billing post-balancing, prosument ratio for virtual energy banks, and test harness) are being consolidated in this repository.
