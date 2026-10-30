# Tauron AMIplus

[![GitHub Latest Release](https://img.shields.io/github/v/release/skoczo/Home-Assistant-custom-components-Tauron-AMIplus)](https://github.com/skoczo/Home-Assistant-custom-components-Tauron-AMIplus/releases)
[![Test](https://github.com/skoczo/Home-Assistant-custom-components-Tauron-AMIplus/actions/workflows/test.yaml/badge.svg)](https://github.com/skoczo/Home-Assistant-custom-components-Tauron-AMIplus/actions/workflows/test.yaml)
[![codecov](https://codecov.io/gh/skoczo/Home-Assistant-custom-components-Tauron-AMIplus/graph/badge.svg)](https://codecov.io/gh/skoczo/Home-Assistant-custom-components-Tauron-AMIplus)
[![Validate HACS](https://github.com/skoczo/Home-Assistant-custom-components-Tauron-AMIplus/actions/workflows/hacs.yaml/badge.svg)](https://github.com/skoczo/Home-Assistant-custom-components-Tauron-AMIplus/actions/workflows/hacs.yaml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)

Home Assistant custom integration for retrieving energy consumption and generation data from Polish electrical utility DSO portal [TAURON eLicznik](https://elicznik.tauron-dystrybucja.pl).


> **Note on maintenance:**  
> This repository is a maintained continuation (fork) of the original component created by [Piotr Machowski](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus). As the upstream project has become inactive, this fork aims to ensure compatibility with modern Home Assistant versions (2025.x / 2026.x+), resolve outstanding bugs, and incorporate improvements contributed by the community.

---

## Features

- **Long-Term Statistics for Energy Dashboard:** Automatically records hourly consumption, generation, and net balance into Home Assistant Recorder under the `tauron_importer:` domain.
- **Tariff Support:** Works with single-zone and multi-zone tariffs (e.g. G11, G12, G12w, G13) with breakdown by tariff zone (T1, T2, T3).
- **Aggregated Sensors:** Daily, monthly, yearly, and last-12-month energy totals.
- **Safe Polling:** Respects TAURON's rate limits with built-in session caching and conservative polling intervals.

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant instance.
2. Go to **Integrations**, click the top-right menu (three dots), and select **Custom repositories**.
3. Add the repository URL:
   ```text
   https://github.com/skoczo/Home-Assistant-custom-components-Tauron-AMIplus
   ```
   Category: **Integration**.
4. Search for **Tauron AMIplus**, download the integration, and restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest `tauron_amiplus.zip` from the [Releases](https://github.com/skoczo/Home-Assistant-custom-components-Tauron-AMIplus/releases) page.
2. Extract the archive into your Home Assistant directory under:
   ```text
   config/custom_components/tauron_amiplus
   ```
3. Restart Home Assistant.

---

## Configuration

The integration is configured entirely through the Home Assistant UI:

1. In Home Assistant, navigate to **Settings** -> **Devices & Services** -> **Add Integration**.
2. Search for **Tauron AMIplus** (or use the link below).
3. Enter your login credentials for the [TAURON eLicznik](https://elicznik.tauron-dystrybucja.pl) portal.
4. Select your electricity meter from the list of detected meters.
5. Choose your desired optional sensors (generation, balance, long-term statistics).

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tauron_amiplus)

---

## Energy Dashboard Setup

To display hourly data in the **Home Assistant Energy Dashboard**:

1. Go to **Settings** -> **Dashboards** -> **Energy**.
2. In the **Electricity grid** card:
   - For consumption, select the statistic: `tauron_importer:<meter_id>_consumption`
   - For generation (if applicable), select: `tauron_importer:<meter_id>_generation`
3. If using a multi-zone tariff (like G12 or G13), you can add individual zone statistics (e.g. `tauron_importer:<meter_id>_consumption_zone_1`).

*Note: Do not select the regular entity (`sensor.tauron_...`), as regular entities only hold aggregated values. Select the statistic starting with `tauron_importer:`.*

---

## Services

- `tauron_amiplus.download_statistics`: Allows manually triggering a historical data import from a specified start date to backfill missing days.
- `tauron_amiplus.clear_cache`: Clears the in-memory cached daily readings for a specific device.

---

## FAQ

- **When does the integration refresh data?**  
  TAURON eLicznik updates readings once or twice a day with a 1–2 day delay. The integration polls eLicznik on a conservative 8.5-hour schedule to prevent automated account lockouts.

- **Why is data missing for yesterday or today?**  
  TAURON does not provide real-time data. Readings for the previous day usually appear in eLicznik late the following morning or afternoon.

- **How can I fill gaps in historical statistics?**  
  Once data is visible in the eLicznik web portal, call the `tauron_amiplus.download_statistics` service from Developer Tools -> Services, passing your device ID and the desired start date.

---

## Credits & License

- Original integration created and developed by [Piotr Machowski](https://github.com/PiotrMachowski).
- Maintained and updated by [Adrian Skoczylas (@skoczo)](https://github.com/skoczo) and community contributors.
- Licensed under the [MIT License](LICENSE).