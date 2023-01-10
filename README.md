[![HACS Default][hacs_shield]][hacs]
[![GitHub Latest Release][releases_shield]][latest_release]
[![GitHub All Releases][downloads_total_shield]][releases]
[![Ko-Fi][ko_fi_shield]][ko_fi]
[![PayPal.Me][paypal_me_shield]][paypal_me]


[hacs_shield]: https://img.shields.io/static/v1.svg?label=HACS&message=Default&style=popout&color=green&labelColor=41bdf5&logo=HomeAssistantCommunityStore&logoColor=white
[hacs]: https://hacs.xyz/docs/default_repositories

[latest_release]: https://github.com/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/releases/latest
[releases_shield]: https://img.shields.io/github/release/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus.svg?style=popout

[releases]: https://github.com/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/releases
[downloads_total_shield]: https://img.shields.io/github/downloads/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/total

[ko_fi_shield]: https://img.shields.io/static/v1.svg?label=%20&message=Ko-Fi&color=F16061&logo=ko-fi&logoColor=white
[ko_fi]: https://ko-fi.com/piotrmachowski

[buy_me_a_coffee_shield]: https://img.shields.io/static/v1.svg?label=%20&message=Buy%20me%20a%20coffee&color=6f4e37&logo=buy%20me%20a%20coffee&logoColor=white
[buy_me_a_coffee]: https://www.buymeacoffee.com/PiotrMachowski

[paypal_me_shield]: https://img.shields.io/static/v1.svg?label=%20&message=PayPal.Me&logo=paypal
[paypal_me]: https://paypal.me/PiMachowski


# Tauron AMIplus sensor

This sensor uses unofficial API to get energy usage and generation data from [*TAURON eLicznik*](https://elicznik.tauron-dystrybucja.pl).

## Configuration

### Config flow (recommended)

To configure this integration go to: _Configuration_ -> _Integrations_ -> _Add integration_ -> _Tauron AMIplus_.

You can also use following [My Home Assistant](http://my.home-assistant.io/) link

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tauron_amiplus)

### Manual - yaml

| Key | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `name` | `string` | `False` | `Tauron AMIPlus` | Name of sensor |
| `username` | `string` | `True` | - | Username used to login at [*eLicznik*](https://elicznik.tauron-dystrybucja.pl) |
| `password` | `string` | `True` | - | Password used to login at [*eLicznik*](https://elicznik.tauron-dystrybucja.pl) |
| `energy_meter_id` | `string` | `True` | - | ID of energy meter |
| `check_generation` | `boolean` | `False` | `false` | Enables checking energy generation |
| `monitored_variables` | `list` | `True` | - | List of variables to monitor |

### Possible monitored conditions

| Key | Description |
| --- | --- | 
| `current_readings` | Current readings of a meter |
| `consumption_daily` | Daily energy consumption **(for previous day!)** |
| `consumption_monthly` | Monthly energy consumption |
| `consumption_yearly` | Yearly energy consumption |
| `generation_daily` | Daily energy generation **(for previous day!)** |
| `generation_monthly` | Monthly energy generation |
| `generation_yearly` | Yearly energy generation |

## Example usage

```
sensor:
  - platform: tauron_amiplus
    name: Tauron AMIPlus
    username: !secret tauron_amiplus.username
    password: !secret tauron_amiplus.password
    energy_meter_id: !secret tauron_amiplus.energy_meter_id
    check_generation: true
    monitored_variables:
      - current_readings
      - consumption_daily
      - consumption_monthly
      - consumption_yearly
      - generation_daily
      - generation_monthly
      - generation_yearly
```

## Installation

### Using [HACS](https://hacs.xyz/) (recommended)

* In _Integrations_ section add repository "Tauron AMIplus"
* Install added repository
 
### Manual

Download [*tauron_amiplus.zip*](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/releases/latest/download/tauron_amiplus.zip) and extract its contents to `config/custom_components/tauron_amiplus` directory:
```bash
mkdir -p custom_components/tauron_amiplus
cd custom_components/tauron_amiplus
wget https://github.com/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/releases/latest/download/tauron_amiplus.zip
unzip tauron_amiplus.zip
rm tauron_amiplus.zip
```

Then restart Home Assistant before applying configuration file changes.

## FAQ

* **How to get energy meter id?**
  
  To find out value for `energy_meter_id` log in to [_*eLicznik*_](https://elicznik.tauron-dystrybucja.pl). Desired value is in upper-left corner of page (Punkt poboru).

<a href='https://ko-fi.com/piotrmachowski' target='_blank'><img height='35' style='border:0px;height:46px;' src='https://az743702.vo.msecnd.net/cdn/kofi3.png?v=0' border='0' alt='Buy Me a Coffee at ko-fi.com' />
<a href="https://paypal.me/PiMachowski" target="_blank"><img src="https://www.paypalobjects.com/webstatic/mktg/logo/pp_cc_mark_37x23.jpg" border="0" alt="PayPal Logo" style="height: auto !important;width: auto !important;"></a>