"""Constants for tauron."""
from datetime import timedelta

DOMAIN = "tauron_amiplus"
DEFAULT_NAME = "Tauron AMIplus"
DATA_TAURON_CLIENT = "data_client"
CONF_METER_ID = "energy_meter_id"
CONF_GENERATION = "check_generation"
CONF_TARIFF = "tariff"
CONF_SHOW_GENERATION = "show_generation_sensors"
CONF_URL_SERVICE = "https://elicznik.tauron-dystrybucja.pl"
CONF_URL_LOGIN = "https://logowanie.tauron-dystrybucja.pl/login"
CONF_URL_CHARTS = "https://elicznik.tauron-dystrybucja.pl/index/charts"
CONF_URL_READINGS = "https://elicznik.tauron-dystrybucja.pl/readings/getread"
CONF_REQUEST_HEADERS = {"cache-control": "no-cache"}
CONF_REQUEST_PAYLOAD_CHARTS = {"dane[cache]": 0}
TYPE_ZONE = "zone"
TYPE_CONSUMPTION_TOTAL = "consumption_total"
TYPE_CONSUMPTION_DAILY = "consumption_daily"
TYPE_CONSUMPTION_MONTHLY = "consumption_monthly"
TYPE_CONSUMPTION_YEARLY = "consumption_yearly"
TYPE_GENERATION_DAILY = "generation_daily"
TYPE_GENERATION_MONTHLY = "generation_monthly"
TYPE_GENERATION_YEARLY = "generation_yearly"
ZONE = "zone"
TARIFF_G12 = "G12"
SUPPORTED_TARIFFS = [TARIFF_G12]
DEFAULT_UPDATE_INTERVAL = timedelta(hours=12)
SENSOR_TYPES = {
    TYPE_ZONE: [None, "sum", ("generation", "OZEValue"), "Zone"],
    TYPE_CONSUMPTION_TOTAL: [
        "kWh",
        None,
        (None, None),
        "Total energy consumption",
    ],
    TYPE_CONSUMPTION_DAILY: [
        timedelta(hours=24),
        "kWh",
        "sum",
        ("generation", "OZEValue"),
        "Daily energy consumption",
    ],
    TYPE_CONSUMPTION_MONTHLY: [
        timedelta(hours=1),
        "kWh",
        "sum",
        ("generation", "OZEValue"),
        "Monthly energy consumption",
    ],
    TYPE_CONSUMPTION_YEARLY: [
        timedelta(hours=24),
        "kWh",
        "sum",
        ("generation", "OZEValue"),
        "Yearly energy consumption",
    ],
    TYPE_GENERATION_DAILY: [
        timedelta(hours=24),
        "kWh",
        "OZEValue",
        ("consumption", "sum"),
        "Daily energy generation",
    ],
    TYPE_GENERATION_MONTHLY: [
        timedelta(hours=24),
        "kWh",
        "OZEValue",
        ("consumption", "sum"),
        "Monthly energy generation",
    ],
    TYPE_GENERATION_YEARLY: [
        timedelta(hours=24),
        "kWh",
        "OZEValue",
        ("consumption", "sum"),
        "Yearly energy generation",
    ],
}
