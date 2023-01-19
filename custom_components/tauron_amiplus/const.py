"""Constants for tauron."""
from datetime import timedelta

DOMAIN = "tauron_amiplus"
STATISTICS_DOMAIN = "tauron_importer"
DEFAULT_NAME = "Tauron AMIplus"
DATA_TAURON_CLIENT = "data_client"
CONF_METER_ID = "energy_meter_id"
CONF_TARIFF = "tariff"
CONF_SHOW_GENERATION = "show_generation_sensors"
CONST_DATE_FORMAT = "%d.%m.%Y"
CONST_MAX_LOOKUP_RANGE = 7
CONST_URL_LOGIN = "https://logowanie.tauron-dystrybucja.pl/login"
CONST_URL_SERVICE = "https://elicznik.tauron-dystrybucja.pl"
CONST_URL_SELECT_METER = f"{CONST_URL_SERVICE}/ustaw_punkt"
CONST_URL_ENERGY = f"{CONST_URL_SERVICE}/energia/api"
CONST_URL_READINGS = f"{CONST_URL_SERVICE}/odczyty/api"
CONST_REQUEST_HEADERS = {"cache-control": "no-cache"}
CONST_CONSUMPTION = "consumption"
CONST_GENERATION = "generation"
CONST_BALANCED = "balanced"
CONST_READING = "reading"
CONST_DAILY = "daily"
CONST_MONTHLY = "monthly"
CONST_YEARLY = "yearly"
CONST_LAST_12_MONTHS = "last_12_months"
TYPE_BALANCED_DAILY = f"{CONST_BALANCED}_{CONST_DAILY}"
TYPE_BALANCED_MONTHLY = f"{CONST_BALANCED}_{CONST_MONTHLY}"
TYPE_CONSUMPTION_READING = f"{CONST_CONSUMPTION}_{CONST_READING}"
TYPE_CONSUMPTION_DAILY = f"{CONST_CONSUMPTION}_{CONST_DAILY}"
TYPE_CONSUMPTION_MONTHLY = f"{CONST_CONSUMPTION}_{CONST_MONTHLY}"
TYPE_CONSUMPTION_YEARLY = f"{CONST_CONSUMPTION}_{CONST_YEARLY}"
TYPE_CONSUMPTION_LAST_12_MONTHS = f"{CONST_CONSUMPTION}_{CONST_LAST_12_MONTHS}"
TYPE_GENERATION_READING = f"{CONST_GENERATION}_{CONST_READING}"
TYPE_GENERATION_DAILY = f"{CONST_GENERATION}_{CONST_DAILY}"
TYPE_GENERATION_MONTHLY = f"{CONST_GENERATION}_{CONST_MONTHLY}"
TYPE_GENERATION_YEARLY = f"{CONST_GENERATION}_{CONST_YEARLY}"
TYPE_GENERATION_LAST_12_MONTHS = f"{CONST_GENERATION}_{CONST_LAST_12_MONTHS}"

DEFAULT_UPDATE_INTERVAL = timedelta(hours=8, minutes=30)
SENSOR_TYPES = {
    TYPE_CONSUMPTION_READING: [
        "Current consumption reading",
    ],
    TYPE_CONSUMPTION_DAILY: [
        "Daily energy consumption",
    ],
    TYPE_CONSUMPTION_MONTHLY: [
        "Monthly energy consumption",
    ],
    TYPE_CONSUMPTION_YEARLY: [
        "Yearly energy consumption",
    ],
    TYPE_CONSUMPTION_LAST_12_MONTHS: [
        "Last 12 months energy consumption",
    ],
    TYPE_GENERATION_READING: [
        "Current generation reading",
    ],
    TYPE_GENERATION_DAILY: [
        "Daily energy generation",
    ],
    TYPE_GENERATION_MONTHLY: [
        "Monthly energy generation",
    ],
    TYPE_GENERATION_YEARLY: [
        "Yearly energy generation",
    ],
    TYPE_GENERATION_LAST_12_MONTHS: [
        "Last 12 months energy generation",
    ],
    TYPE_BALANCED_DAILY: [
        "Daily balance"
    ],
    TYPE_BALANCED_MONTHLY: [
        "Monthly balance"
    ]
}
