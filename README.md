[![HACS Default][hacs_shield]][hacs]
[![GitHub Latest Release][releases_shield]][latest_release]
[![GitHub All Releases][downloads_total_shield]][releases]<!-- piotrmachowski_support_badges_start -->
[![Ko-Fi][ko_fi_shield]][ko_fi]
[![buycoffee.to][buycoffee_to_shield]][buycoffee_to]
[![PayPal.Me][paypal_me_shield]][paypal_me]
[![Revolut.Me][revolut_me_shield]][revolut_me]
<!-- piotrmachowski_support_badges_end -->



[hacs_shield]: https://img.shields.io/static/v1.svg?label=HACS&message=Default&style=popout&color=green&labelColor=41bdf5&logo=HomeAssistantCommunityStore&logoColor=white
[hacs]: https://hacs.xyz/docs/default_repositories

[latest_release]: https://github.com/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/releases/latest
[releases_shield]: https://img.shields.io/github/release/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus.svg?style=popout

[releases]: https://github.com/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/releases
[downloads_total_shield]: https://img.shields.io/github/downloads/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/total


# Tauron AMIplus sensor

This sensor uses unofficial API to get energy usage and generation data from [*TAURON eLicznik*](https://elicznik.tauron-dystrybucja.pl).

## Configuration

### Config flow (recommended)

To configure this integration go to: _Configuration_ -> _Integrations_ -> _Add integration_ -> _Tauron AMIplus_.

You can also use following [My Home Assistant](http://my.home-assistant.io/) link

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tauron_amiplus)

### Manual - yaml


<details>
<summary>Warning: yaml configuration is not recommended</summary>


**Warning:** Not all features are available when using yaml configuration

| Key                   | Type     | Required | Default          | Description                                                                    |
|-----------------------|----------|----------|------------------|--------------------------------------------------------------------------------|
| `name`                | `string` | `False`  | `Tauron AMIPlus` | Name of sensor                                                                 |
| `username`            | `string` | `True`   | -                | Username used to login at [*eLicznik*](https://elicznik.tauron-dystrybucja.pl) |
| `password`            | `string` | `True`   | -                | Password used to login at [*eLicznik*](https://elicznik.tauron-dystrybucja.pl) |
| `energy_meter_id`     | `string` | `True`   | -                | ID of energy meter                                                             |
| `monitored_variables` | `list`   | `True`   | -                | List of variables to monitor                                                   |

#### Possible monitored conditions

| Key                          | Description                                      |
|------------------------------|--------------------------------------------------| 
| `consumption_reading`        | Current consumption reading of a meter           |
| `consumption_daily`          | Daily energy consumption **(for previous day!)** |
| `consumption_monthly`        | Monthly energy consumption                       |
| `consumption_yearly`         | Yearly energy consumption                        |
| `consumption_last_12_months` | Total energy consumption for last 12 months      |
| `generation_reading`         | Current generation reading of a meter            |
| `generation_daily`           | Daily energy generation **(for previous day!)**  |
| `generation_monthly`         | Monthly energy generation                        |
| `generation_yearly`          | Yearly energy generation                         |
| `generation_last_12_months`  | Total energy generation for last 12 months       |
| `balanced_daily`             | Daily balance **(for previous day!)**            |
| `balanced_monthly`           | Monthly balance                                  |
| `balanced_yearly`            | Yearly balance                                   |
| `balanced_last_12_months`    | Balance for last 12 months                       |

#### Example usage

```
sensor:
  - platform: tauron_amiplus
    name: Tauron AMIPlus
    username: !secret tauron_amiplus.username
    password: !secret tauron_amiplus.password
    energy_meter_id: !secret tauron_amiplus.energy_meter_id
    monitored_variables:
      - consumption_reading
      - consumption_daily
      - consumption_monthly
      - consumption_yearly
      - consumption_last_12_months
      - generation_reading
      - generation_daily
      - generation_monthly
      - generation_yearly
      - generation_last_12_months
      - balanced_daily
      - balanced_monthly
      - balanced_yearly
      - balanced_last_12_months
```


</details>


## Installation


<table><tr><th>Since v2.3.0 this integration requires Home Assistant version 2022.12 or latter</th></tr></table>
<table><tr><th>Since v2.4.8 this integration might cause slow starts of Home Assistant</th></tr></table>


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

* **How to display hourly data in Energy dashboard?**

  To show hourly data in Energy dashboard you have to use `tauron_importer` positions.

* **Why there are missing days in statistics/Energy dashboard?**

  Such gaps appear when there are missing values in hourly readings for this day.
  You can confirm it using [eLicznik website](https://elicznik.tauron-dystrybucja.pl).
  
* **How to fix missing data in statistics/Energy dashboard?**

  Once the data appears on [eLicznik website](https://elicznik.tauron-dystrybucja.pl) can fill such gaps using `tauron_amiplus.download_statistics` service.

* **When does this integration update data?**

  This integration logs in and downloads data from eLicznik website every 8.5h.
  This timer is restarted after: HA restart, integration reload, configuration change.
  Additionally, a new pack of data is freshly downloaded when user retrieves diagnostics data.

* **How to get energy meter id?**
  
  To find out value for `energy_meter_id` follow [these steps](https://github.com/PiotrMachowski/Home-Assistant-custom-components-Tauron-AMIplus/issues/105#issuecomment-1413675239).
  
* **How to calculate available energy as a prosument?**

  To calculate available energy you can use following config:
  ```yaml
  input_number:
    initial_energy_bank:
      min: 0
      max: 100000000
      step: 1
      mode: box
  template:
    - sensor:
        - name: Tauron energy bank
          state_class: total
          device_class: energy
          unique_id: tauron_energy_bank
          icon: mdi:home-battery-outline
          state: "{{ (states('input_number.initial_energy_bank') | float(0) + states('sensor.tauron_amiplus_123_yearly_energy_generation') | float(0) * 0.8 - states('sensor.tauron_amiplus_123_yearly_energy_consumption') | float(0)) | round(3) }}"
          unit_of_measurement: "kWh"
          availability: "{{ states('sensor.tauron_amiplus_123_yearly_energy_generation') | is_number and states('sensor.tauron_amiplus_123_yearly_energy_consumption') | is_number }}"
  ```


<!-- piotrmachowski_support_links_start -->

## Support

If you want to support my work with a donation you can use one of the following platforms:

<table>
  <tr>
    <th>Platform</th>
    <th>Payment methods</th>
    <th>Link</th>
    <th>Comment</th>
  </tr>
  <tr>
    <td>Ko-fi</td>
    <td>
      <li>PayPal</li>
      <li>Credit card</li>
    </td>
    <td>
      <a href='https://ko-fi.com/piotrmachowski' target='_blank'><img height='35px' src='https://az743702.vo.msecnd.net/cdn/kofi3.png?v=0' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
    </td>
    <td>
      <li>No fees</li>
      <li>Single or monthly payment</li>
    </td>
  </tr>
  <tr>
    <td>buycoffee.to</td>
    <td>
      <li>BLIK</li>
      <li>Bank transfer</li>
    </td>
    <td>
      <a href="https://buycoffee.to/piotrmachowski" target="_blank"><img src="https://buycoffee.to/btn/buycoffeeto-btn-primary.svg" height="35px" alt="Postaw mi kawę na buycoffee.to"></a>
    </td>
    <td></td>
  </tr>
  <tr>
    <td>PayPal</td>
    <td>
      <li>PayPal</li>
    </td>
    <td>
      <a href="https://paypal.me/PiMachowski" target="_blank"><img src="https://www.paypalobjects.com/webstatic/mktg/logo/pp_cc_mark_37x23.jpg" border="0" alt="PayPal Logo" height="35px" style="height: auto !important;width: auto !important;"></a>
    </td>
    <td>
      <li>No fees</li>
    </td>
  </tr>
  <tr>
    <td>Revolut</td>
    <td>
      <li>Revolut</li>
      <li>Credit Card</li>
    </td>
    <td>
      <a href="https://revolut.me/314ma" target="_blank"><img src="https://www.revolut.com/favicon/android-chrome-192x192.png" height="35px" alt="Revolut"></a>
    </td>
    <td>
      <li>No fees</li>
    </td>
  </tr>
</table>


[ko_fi_shield]: https://img.shields.io/static/v1.svg?label=%20&message=Ko-Fi&color=F16061&logo=ko-fi&logoColor=white

[ko_fi]: https://ko-fi.com/piotrmachowski

[buycoffee_to_shield]: https://shields.io/badge/buycoffee.to-white?style=flat&labelColor=white&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAABhmlDQ1BJQ0MgcHJvZmlsZQAAKJF9kT1Iw1AUhU9TpaIVh1YQcchQnayIijhKFYtgobQVWnUweemP0KQhSXFxFFwLDv4sVh1cnHV1cBUEwR8QVxcnRRcp8b6k0CLGC4/3cd49h/fuA4R6malmxzigapaRisfEbG5FDLzChxB6MIZ+iZl6Ir2QgWd93VM31V2UZ3n3/Vm9St5kgE8knmW6YRGvE09vWjrnfeIwK0kK8TnxqEEXJH7kuuzyG+eiwwLPDBuZ1BxxmFgstrHcxqxkqMRTxBFF1ShfyLqscN7irJarrHlP/sJgXltOc53WEOJYRAJJiJBRxQbKsBClXSPFRIrOYx7+QcefJJdMrg0wcsyjAhWS4wf/g9+zNQuTE25SMAZ0vtj2xzAQ2AUaNdv+PrbtxgngfwautJa/UgdmPkmvtbTIEdC3DVxctzR5D7jcAQaedMmQHMlPSygUgPcz+qYcELoFulfduTXPcfoAZGhWSzfAwSEwUqTsNY93d7XP7d+e5vx+AIahcq//o+yoAAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH5wETCy4vFNqLzwAAAVpJREFUOMvd0rFLVXEYxvHPOedKJnKJhrDLuUFREULE7YDCMYj+AydpsCWiaKu29hZxiP4Al4aWwC1EdFI4Q3hqEmkIBI8ZChWXKNLLvS0/Qcza84V3enm/7/s878t/HxGkeTaIGziP+EB918nawu7Dq1d0e1+2J2bepnk2jFEUVVF+qKV51o9neBCaugfge70keoxxUbSWjrQ+4SUyzKZ5NlnDZdzGG7w4DIh+dtZEFntDA98l8S0MYwctNGrYz9WqKJePFLq80g5Sr+EHlnATp+NA+4qLaZ7FfzMrzbMBjGEdq8GrJMZnvAvFC/8wfAwjWMQ8XmMzaW9sdevNRgd3MFhvNpbaG1u/Dk2/hOc4gadVUa7Um425qii/7Z+xH9O4jwW8Cqv24Tru4hyeVEU588cfBMgpPMI9nMFe0BkFzVOYrYqycyQgQJLwTC2cDZCPeF8V5Y7jGb8BUpRicy7OU5MAAAAASUVORK5CYII=

[buycoffee_to]: https://buycoffee.to/piotrmachowski

[buy_me_a_coffee_shield]: https://img.shields.io/static/v1.svg?label=%20&message=Buy%20me%20a%20coffee&color=6f4e37&logo=buy%20me%20a%20coffee&logoColor=white

[buy_me_a_coffee]: https://www.buymeacoffee.com/PiotrMachowski

[paypal_me_shield]: https://img.shields.io/static/v1.svg?label=%20&message=PayPal.Me&logo=paypal

[paypal_me]: https://paypal.me/PiMachowski

[revolut_me_shield]: https://img.shields.io/static/v1.svg?label=%20&message=Revolut&logo=revolut

[revolut_me]: https://revolut.me/314ma
<!-- piotrmachowski_support_links_end -->