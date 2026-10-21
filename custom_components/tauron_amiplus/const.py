"""Constants for tauron."""
from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import Platform, UnitOfEnergy, UnitOfReactiveEnergy

PLATFORMS = [Platform.SENSOR]
DOMAIN = "tauron_amiplus"
STATISTICS_DOMAIN = "tauron_importer"
DEFAULT_NAME = "Tauron AMIplus"
DATA_TAURON_CLIENT = "data_client"
CONF_METER_ID = "energy_meter_id"
CONF_METER_NAME = "energy_meter_name"
CONF_TARIFF = "tariff"
CONF_SHOW_GENERATION = "show_generation_sensors"
CONF_SHOW_BALANCED = "show_balanced_sensors"
CONF_SHOW_BALANCED_YEAR = "show_balanced_year_sensors"
CONF_SHOW_12_MONTHS = "show_12_months_sensors"
CONF_SHOW_CONFIGURABLE = "show_configurable_sensors"
CONF_SHOW_CONFIGURABLE_DATE = "show_configurable_sensors_date"
CONF_SHOW_REACTIVE = "show_reactive_sensors"
CONF_SHOW_NET_BILLING = "show_net_billing_sensors"
CONF_STORE_STATISTICS = "store_statistics"
CONST_DATE_FORMAT = "%d.%m.%Y"
CONST_MAX_LOOKUP_RANGE = 7
CONST_URL_LOGIN = "https://logowanie.tauron-dystrybucja.pl/login"
CONST_URL_SERVICE = "https://elicznik.tauron-dystrybucja.pl"
CONST_URL_LOGIN_MOJ_TAURON = "https://logowanie.tauron.pl/login"
CONST_URL_SERVICE_MOJ_TAURON = "https://moj.tauron.pl"
CONST_URL_SELECT_METER = f"{CONST_URL_SERVICE}/ustaw_punkt"
CONST_URL_ENERGY = f"{CONST_URL_SERVICE}/energia/api"
CONST_URL_READINGS = f"{CONST_URL_SERVICE}/odczyty/api"
CONST_URL_ENERGY_BUSINESS = f"{CONST_URL_SERVICE}/energia/wo/api"
CONST_REQUEST_HEADERS = {"cache-control": "no-cache"}
CONST_CONSUMPTION = "consumption"
CONST_GENERATION = "generation"
CONST_REACTIVE_INDUCTIVE = "reactive_inductive"
CONST_REACTIVE_CAPACITIVE = "reactive_capacitive"
CONST_NET_CONSUMPTION = "net_consumption"
CONST_NET_GENERATION = "net_generation"
CONST_BALANCED = "balanced"
CONST_READING = "reading"
CONST_DAILY = "daily"
CONST_MONTHLY = "monthly"
CONST_YEARLY = "yearly"
CONST_LAST_12_MONTHS = "last_12_months"
CONST_CONFIGURABLE = "configurable"
STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_session_data"

# Mapping of internal data kinds to the "type" POST parameter accepted by
# elicznik.tauron-dystrybucja.pl/energia/api, as captured from real site traffic.
API_TYPE_BY_DATA_KIND = {
    CONST_CONSUMPTION: "consum",
    CONST_GENERATION: "oze",
    CONST_REACTIVE_INDUCTIVE: "indukcyjna",
    CONST_REACTIVE_CAPACITIVE: "pojemnosciowa",
    CONST_NET_CONSUMPTION: "netto",
    CONST_NET_GENERATION: "netto_oze",
}
# The site no longer sends "energy" at all for the new types; kept only for
# consumption/generation to avoid changing already-working behaviour.
ENERGY_PARAM_BY_DATA_KIND = {
    CONST_CONSUMPTION: 1,
    CONST_GENERATION: 2,
}
# Unit / device class / recorder unit_class per data kind, shared by sensor.py and statistics.py.
UNIT_INFO_BY_DATA_KIND = {
    CONST_CONSUMPTION: (UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, "energy"),
    CONST_GENERATION: (UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, "energy"),
    CONST_NET_CONSUMPTION: (UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, "energy"),
    CONST_NET_GENERATION: (UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, "energy"),
    CONST_REACTIVE_INDUCTIVE: (
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        SensorDeviceClass.REACTIVE_ENERGY,
        "reactive_energy",
    ),
    CONST_REACTIVE_CAPACITIVE: (
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        SensorDeviceClass.REACTIVE_ENERGY,
        "reactive_energy",
    ),
}

TYPE_BALANCED_DAILY = f"{CONST_BALANCED}_{CONST_DAILY}"
TYPE_BALANCED_MONTHLY = f"{CONST_BALANCED}_{CONST_MONTHLY}"
TYPE_BALANCED_YEARLY = f"{CONST_BALANCED}_{CONST_YEARLY}"
TYPE_BALANCED_LAST_12_MONTHS = f"{CONST_BALANCED}_{CONST_LAST_12_MONTHS}"
TYPE_BALANCED_CONFIGURABLE = f"{CONST_BALANCED}_{CONST_CONFIGURABLE}"
TYPE_CONSUMPTION_READING = f"{CONST_CONSUMPTION}_{CONST_READING}"
TYPE_CONSUMPTION_DAILY = f"{CONST_CONSUMPTION}_{CONST_DAILY}"
TYPE_CONSUMPTION_MONTHLY = f"{CONST_CONSUMPTION}_{CONST_MONTHLY}"
TYPE_CONSUMPTION_YEARLY = f"{CONST_CONSUMPTION}_{CONST_YEARLY}"
TYPE_CONSUMPTION_LAST_12_MONTHS = f"{CONST_CONSUMPTION}_{CONST_LAST_12_MONTHS}"
TYPE_CONSUMPTION_CONFIGURABLE = f"{CONST_CONSUMPTION}_{CONST_CONFIGURABLE}"
TYPE_GENERATION_READING = f"{CONST_GENERATION}_{CONST_READING}"
TYPE_GENERATION_DAILY = f"{CONST_GENERATION}_{CONST_DAILY}"
TYPE_GENERATION_MONTHLY = f"{CONST_GENERATION}_{CONST_MONTHLY}"
TYPE_GENERATION_YEARLY = f"{CONST_GENERATION}_{CONST_YEARLY}"
TYPE_GENERATION_LAST_12_MONTHS = f"{CONST_GENERATION}_{CONST_LAST_12_MONTHS}"
TYPE_GENERATION_CONFIGURABLE = f"{CONST_GENERATION}_{CONST_CONFIGURABLE}"
TYPE_REACTIVE_INDUCTIVE_DAILY = f"{CONST_REACTIVE_INDUCTIVE}_{CONST_DAILY}"
TYPE_REACTIVE_INDUCTIVE_MONTHLY = f"{CONST_REACTIVE_INDUCTIVE}_{CONST_MONTHLY}"
TYPE_REACTIVE_INDUCTIVE_YEARLY = f"{CONST_REACTIVE_INDUCTIVE}_{CONST_YEARLY}"
TYPE_REACTIVE_INDUCTIVE_LAST_12_MONTHS = f"{CONST_REACTIVE_INDUCTIVE}_{CONST_LAST_12_MONTHS}"
TYPE_REACTIVE_CAPACITIVE_DAILY = f"{CONST_REACTIVE_CAPACITIVE}_{CONST_DAILY}"
TYPE_REACTIVE_CAPACITIVE_MONTHLY = f"{CONST_REACTIVE_CAPACITIVE}_{CONST_MONTHLY}"
TYPE_REACTIVE_CAPACITIVE_YEARLY = f"{CONST_REACTIVE_CAPACITIVE}_{CONST_YEARLY}"
TYPE_REACTIVE_CAPACITIVE_LAST_12_MONTHS = f"{CONST_REACTIVE_CAPACITIVE}_{CONST_LAST_12_MONTHS}"
TYPE_NET_CONSUMPTION_DAILY = f"{CONST_NET_CONSUMPTION}_{CONST_DAILY}"
TYPE_NET_CONSUMPTION_MONTHLY = f"{CONST_NET_CONSUMPTION}_{CONST_MONTHLY}"
TYPE_NET_CONSUMPTION_YEARLY = f"{CONST_NET_CONSUMPTION}_{CONST_YEARLY}"
TYPE_NET_CONSUMPTION_LAST_12_MONTHS = f"{CONST_NET_CONSUMPTION}_{CONST_LAST_12_MONTHS}"
TYPE_NET_GENERATION_DAILY = f"{CONST_NET_GENERATION}_{CONST_DAILY}"
TYPE_NET_GENERATION_MONTHLY = f"{CONST_NET_GENERATION}_{CONST_MONTHLY}"
TYPE_NET_GENERATION_YEARLY = f"{CONST_NET_GENERATION}_{CONST_YEARLY}"
TYPE_NET_GENERATION_LAST_12_MONTHS = f"{CONST_NET_GENERATION}_{CONST_LAST_12_MONTHS}"
TYPE_AMOUNT = "moj_tauron"
TYPE_AMOUNT_PAYMENT = f"{TYPE_AMOUNT}_PAYMENT"

DEFAULT_UPDATE_INTERVAL = timedelta(hours=8, minutes=30)
SENSOR_TYPES_YAML = {
    TYPE_CONSUMPTION_READING: {
        "name": "Current consumption reading",
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    TYPE_CONSUMPTION_DAILY: {
        "name": "Daily energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_CONSUMPTION_MONTHLY: {
        "name": "Monthly energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_CONSUMPTION_YEARLY: {
        "name": "Yearly energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_CONSUMPTION_LAST_12_MONTHS: {
        "name": "Last 12 months energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_GENERATION_READING: {
        "name": "Current generation reading",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_GENERATION_DAILY: {
        "name": "Daily energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_GENERATION_MONTHLY: {
        "name": "Monthly energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_GENERATION_YEARLY: {
        "name": "Yearly energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_GENERATION_LAST_12_MONTHS: {
        "name": "Last 12 months energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_BALANCED_DAILY: {
        "name": "Daily balance",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_BALANCED_MONTHLY: {
        "name": "Monthly balance",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_BALANCED_YEARLY: {
        "name": "Yearly balance",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_BALANCED_LAST_12_MONTHS: {
        "name": "Last 12 months balance",
        "state_class": SensorStateClass.TOTAL,
    },
}
SENSOR_TYPES = {
    **SENSOR_TYPES_YAML,
    TYPE_CONSUMPTION_CONFIGURABLE: {
        "name": "Configurable energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_GENERATION_CONFIGURABLE: {
        "name": "Configurable energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_BALANCED_CONFIGURABLE: {
        "name": "Configurable balance",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_REACTIVE_INDUCTIVE_DAILY: {
        "name": "Daily reactive inductive energy",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_REACTIVE_INDUCTIVE_MONTHLY: {
        "name": "Monthly reactive inductive energy",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_REACTIVE_INDUCTIVE_YEARLY: {
        "name": "Yearly reactive inductive energy",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_REACTIVE_INDUCTIVE_LAST_12_MONTHS: {
        "name": "Last 12 months reactive inductive energy",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_REACTIVE_CAPACITIVE_DAILY: {
        "name": "Daily reactive capacitive energy",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_REACTIVE_CAPACITIVE_MONTHLY: {
        "name": "Monthly reactive capacitive energy",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_REACTIVE_CAPACITIVE_YEARLY: {
        "name": "Yearly reactive capacitive energy",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_REACTIVE_CAPACITIVE_LAST_12_MONTHS: {
        "name": "Last 12 months reactive capacitive energy",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_NET_CONSUMPTION_DAILY: {
        "name": "Daily net-billed energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_NET_CONSUMPTION_MONTHLY: {
        "name": "Monthly net-billed energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_NET_CONSUMPTION_YEARLY: {
        "name": "Yearly net-billed energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_NET_CONSUMPTION_LAST_12_MONTHS: {
        "name": "Last 12 months net-billed energy consumption",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_NET_GENERATION_DAILY: {
        "name": "Daily net-billed energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_NET_GENERATION_MONTHLY: {
        "name": "Monthly net-billed energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_NET_GENERATION_YEARLY: {
        "name": "Yearly net-billed energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    TYPE_NET_GENERATION_LAST_12_MONTHS: {
        "name": "Last 12 months net-billed energy generation",
        "state_class": SensorStateClass.TOTAL,
    },
    # TYPE_AMOUNT_PAYMENT: {
    #     "name": "Account balance",
    #     "state_class": SensorStateClass.MEASUREMENT,
    # },
}
