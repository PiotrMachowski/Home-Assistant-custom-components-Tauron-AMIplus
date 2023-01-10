"""Update coordinator for TAURON sensors."""
import datetime
import logging
import ssl

import requests
from requests import adapters
from urllib3 import poolmanager

from .const import (CONF_URL_ENERGY, CONF_URL_LOGIN, CONF_URL_READINGS, CONF_URL_SERVICE)


_LOGGER = logging.getLogger(__name__)


# to fix the SSLError
class TLSAdapter(adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        """Create and initialize the urllib3 PoolManager."""
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        ctx.check_hostname = False
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_context=ctx,
        )


class TauronAmiplusRawData:
    def __init__(self):
        self.json_readings = None
        self.json_daily = None
        self.daily_date = None
        self.json_monthly = None
        self.json_yearly = None
        self.tariff = None


class TauronAmiplusConnector:
    headers = {
        "cache-control": "no-cache",
    }

    def __init__(self, username, password, meter_id, generation):
        self.username = username
        self.password = password
        self.meter_id = meter_id
        self.generation_enabled = generation

    def get_raw_data(self) -> TauronAmiplusRawData:
        data = TauronAmiplusRawData()
        session = self.get_session()
        data.json_readings = self.get_readings(session)
        data.json_daily, data.daily_date = self.get_values_daily(session)
        data.json_monthly = self.get_values_monthly(session)
        data.json_yearly = self.get_values_yearly(session)
        data.tariff = data.json_yearly["data"]["tariff"]
        return data

    def get_session(self):
        payload_login = {
            "username": self.username,
            "password": self.password,
            "service": CONF_URL_SERVICE,
        }
        session = requests.session()
        session.mount("https://", TLSAdapter())
        session.request(
            "POST",
            CONF_URL_LOGIN,
            data=payload_login,
            headers=TauronAmiplusConnector.headers,
        )
        session.request(
            "POST",
            CONF_URL_LOGIN,
            data=payload_login,
            headers=TauronAmiplusConnector.headers,
        )
        # session.request("POST", CONF_URL_SERVICE, data={"smart": self.meter_id}, headers=TauronAmiplusConnector.headers)
        # https://elicznik.tauron-dystrybucja.pl/ustaw_punkt # TODO

        return session

    def calculate_configuration(self, session, days_before=2, throw_on_empty=True):
        json_data, _ = self.get_raw_values_daily(session, days_before)
        if json_data is None:
            if throw_on_empty:
                raise Exception("Failed to login")
            else:
                return None
        tariff = json_data["data"]["tariff"]
        return tariff

    def get_values_yearly(self, session):
        year = datetime.datetime.now().year
        payload = {
            "from": f"1.01.{year}",
            "to": f"31.12.{year}",
            "profile": "year",
            "type": "consum",
        }
        return TauronAmiplusConnector.get_chart_values(session, payload)

    def get_values_monthly(self, session):
        now = datetime.datetime.now()
        month = now.month
        first_day_of_month = now.replace(day=1)
        last_day_of_month = first_day_of_month.replace(month=month % 12 + 1) - datetime.timedelta(days=1)

        payload = {
            "from": first_day_of_month.strftime("%d.%m.%Y"),
            "to": last_day_of_month.strftime("%d.%m.%Y"),
            "profile": "month",
            "type": "consum",
        }
        return TauronAmiplusConnector.get_chart_values(session, payload)

    def get_values_daily(self, session):
        data, day = self.get_raw_values_daily(session, 1)
        if data is None or len(data["data"]["allData"]) < 24:
            data, day = self.get_raw_values_daily(session, 2)
        return data, day

    def get_raw_values_daily(self, session, days_before):
        day = (datetime.datetime.now() - datetime.timedelta(days_before)).strftime("%d.%m.%Y")
        payload = {
            "from": day,
            "to": day,
            "profile": "full time",
            "type": "consum",
        }
        return TauronAmiplusConnector.get_chart_values(session, payload), day

    def get_readings(self, session, days_before=2):
        day = (datetime.datetime.now() - datetime.timedelta(days_before)).strftime("%d.%m.%Y")
        payload = {
                "from": day,
                "to": day,
                "profile": "month",
                "type": "energia-pobrana"
            }
        return TauronAmiplusConnector.execute_post(session, CONF_URL_READINGS, payload)

    @staticmethod
    def get_chart_values(session, payload):
        return TauronAmiplusConnector.execute_post(session, CONF_URL_ENERGY, payload)

    @staticmethod
    def execute_post(session, url, payload):
        response = session.request(
            "POST",
            url,
            data=payload,
            headers=TauronAmiplusConnector.headers,
        )
        if response.status_code == 200 and response.text.startswith('{"success":true'):
            json_data = response.json()
            return json_data
        return None

    @staticmethod
    def calculate_tariff(username, password, meter_id):
        coordinator = TauronAmiplusConnector(username, password, meter_id, False)
        session = coordinator.get_session()
        config = coordinator.calculate_configuration(session)
        if config is not None:
            return config
        raise Exception("Failed to login")
