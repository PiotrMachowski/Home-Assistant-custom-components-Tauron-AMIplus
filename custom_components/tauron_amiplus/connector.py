import asyncio
import copy
import datetime
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Any

from aiohttp import ClientError, ClientOSError, ClientSession, ServerDisconnectedError
# from bs4 import BeautifulSoup
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.util import slugify
from homeassistant.util.dt import as_utc, get_time_zone

from .const import (
    CONST_DATE_FORMAT,
    CONST_MAX_LOOKUP_RANGE,
    CONST_REQUEST_HEADERS,
    CONST_URL_ENERGY,
    CONST_URL_ENERGY_BUSINESS,
    CONST_URL_LOGIN,
    CONST_URL_LOGIN_MOJ_TAURON,
    CONST_URL_READINGS,
    CONST_URL_SELECT_METER,
    CONST_URL_SERVICE,
    CONST_URL_SERVICE_MOJ_TAURON,
    STORAGE_VERSION,
    STORAGE_KEY_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


class TauronAmiplusRawData:
    def __init__(self):
        self.tariff = None
        self.consumption: Optional[TauronAmiplusDataSet] = None
        self.generation: Optional[TauronAmiplusDataSet] = None
        self.payments: Optional[list[MojTauronPaymentData]] = None

    def data_unavailable(self):
        return self.consumption is None or self.generation is None

    @property
    def balance_daily(self):
        if self.data_unavailable() or self.consumption.json_daily is None or self.generation.json_daily is None:
            return None
        return self.consumption.json_daily, self.generation.json_daily

    @property
    def balance_monthly(self):
        if (self.data_unavailable() or self.consumption.json_month_hourly is None or
                self.generation.json_month_hourly is None):
            return None
        return self.consumption.json_month_hourly, self.generation.json_month_hourly

    @property
    def balance_yearly(self):
        if (self.data_unavailable() or self.consumption.json_year_hourly is None or
                self.generation.json_year_hourly is None):
            return None
        return self.consumption.json_year_hourly, self.generation.json_year_hourly

    @property
    def balance_last_12_months_hourly(self):
        if (self.data_unavailable() or
                self.consumption.json_last_12_months_hourly is None or
                self.generation.json_last_12_months_hourly is None):
            return None
        return self.consumption.json_last_12_months_hourly, self.generation.json_last_12_months_hourly

    @property
    def balance_configurable_hourly(self):
        if (self.data_unavailable() or
                self.consumption.json_configurable_hourly is None or
                self.generation.json_configurable_hourly is None):
            return None
        return self.consumption.json_configurable_hourly, self.generation.json_configurable_hourly


class TauronAmiplusDataSet:
    def __init__(self):
        self.json_reading = None
        self.json_daily = None
        self.daily_date = None
        self.json_monthly = None
        self.json_yearly = None
        self.json_month_hourly = None
        self.json_year_hourly = None
        self.json_last_30_days_hourly = None
        self.json_last_12_months_hourly = None
        self.json_configurable_hourly = None


@dataclass
class MojTauronPaymentData:
    value: float
    date: str


class TauronAmiplusConnector:

    def __init__(
        self,
        username: str,
        password: str,
        meter_id: str,
        hass: HomeAssistant | None = None,
        config_entry_id: str = None,
        show_generation: bool = False,
        show_12_months: bool = False,
        show_balanced: bool = False,
        show_balanced_yearly: bool = False,
        show_configurable: bool = False,
        show_configurable_date: datetime.date = None,
    ):
        self._username = username
        self._password = password
        self._meter_id = meter_id
        self._is_business = False
        self.meters = []
        self._show_generation = show_generation
        self._show_12_months = show_12_months
        self._show_balanced = show_balanced
        self._show_balanced_yearly = show_balanced_yearly
        self._show_configurable = show_configurable
        self._show_configurable_date = show_configurable_date
        self._session: ClientSession | None = None
        self._hass = hass
        self._storage_key = f"{STORAGE_KEY_PREFIX}_{config_entry_id}" if config_entry_id is not None else None
        self._cache = DailyDataCache(meter_id, hass, self._storage_key)
        self._cycle_cache: dict[tuple[str, bool], dict | None] = {}
        self._cycle_cache_hits = 0
        self._cycle_downloads = 0

    async def get_raw_data(self) -> TauronAmiplusRawData:
        start_fetch = time.monotonic()
        self._cycle_cache_hits = 0
        self._cycle_downloads = 0
        self._cycle_cache.clear()
        await self._cache.async_load()
        data = TauronAmiplusRawData()
        # data.payments = await self.get_moj_tauron()
        data.tariff = await self.login()
        generation_max_cache = datetime.datetime.now()
        data.consumption, consumption_max_cache = await self.get_data_set(generation=False)
        if self._show_generation or self._show_balanced:
            data.generation, generation_max_cache = await self.get_data_set(generation=True)
        else:
            data.generation = TauronAmiplusDataSet()
        self._cache.delete_older_than(min(consumption_max_cache, generation_max_cache))
        await self._cache.async_save()
        elapsed = time.monotonic() - start_fetch
        _LOGGER.info(
            f"[{self._meter_id}] Data fetch completed in {elapsed:.1f}s: "
            f"{self._cycle_cache_hits} days loaded from cache, {self._cycle_downloads} new days downloaded from Tauron API"
        )
        return data

    async def get_data_set(self, generation) -> Tuple[TauronAmiplusDataSet, datetime.datetime]:
        dataset = TauronAmiplusDataSet()
        dataset.json_reading = await self.get_reading(generation)
        dataset.json_daily, dataset.daily_date = await self.get_values_daily(generation)
        dataset.json_monthly = await self.get_values_monthly(generation)
        dataset.json_yearly = await self.get_values_yearly(generation)
        if self._show_balanced:
            dataset.json_month_hourly = await self.get_values_month_hourly(generation)
        now = datetime.datetime.now()
        cache_max = datetime.datetime.now() - datetime.timedelta(days=366)
        if self._show_12_months:
            dataset.json_last_12_months_hourly = await self.get_values_12_months_hourly(generation)
            cache_max = now.replace(year=now.year - 1) - datetime.timedelta(days=2)
        if self._show_balanced_yearly:
            dataset.json_year_hourly = await self.get_values_year_hourly(generation)
            potential_max = now.replace(day=1, month=1)
            if potential_max < cache_max:
                cache_max = potential_max
        if self._show_configurable and self._show_configurable_date is not None:
            end = datetime.datetime.now()
            start = datetime.datetime.combine(self._show_configurable_date, end.time())
            dataset.json_configurable_hourly = await self.get_raw_values_daily_for_range(start, end, generation)
            potential_max = end - datetime.timedelta(days=2)
            if potential_max < cache_max:
                cache_max = potential_max
        return dataset, cache_max

    async def login_service(self, login_url: str, service: str) -> tuple[ClientSession, str]:
        success, response, session = await self.try_restore_session(service)
        if success:
            _LOGGER.info(f"[{self._meter_id}] Reusing cached session cookies (valid)")
            return session, response

        _LOGGER.info(f"[{self._meter_id}] Session expired or not found. Authenticating via Keycloak OIDC...")
        self.log(f"Logging in... ({service})")

        # Step 1: GET login page to retrieve the Keycloak form action URL.
        # TAURON migrated from CAS to Keycloak (OpenID Connect) — old POST /login returns 404.
        login_page_response = await session.request(
            "GET",
            f"{login_url}?service={service}",
            headers=CONST_REQUEST_HEADERS,
            allow_redirects=True,
        )
        login_page_text = await login_page_response.text()
        self.log(f"LOGIN PAGE STATUS: {login_page_response.status}")

        form_action_match = re.search(r'<form[^>]+id="kc-form-login"[^>]+action="([^"]+)"', login_page_text)
        if form_action_match is None:
            self.log("Keycloak login form not found in response")
            raise Exception("Failed to find login form")
        form_action = form_action_match.group(1).replace("&amp;", "&")
        self.log(f"FORM ACTION: {form_action[:120]}")

        # Step 2: POST credentials to Keycloak, follow redirects back to the service.
        payload_login = {
            "username": self._username,
            "password": self._password,
            "credentialId": "",
        }
        login_response = await session.request(
            "POST",
            form_action,
            data=payload_login,
            headers=CONST_REQUEST_HEADERS,
            allow_redirects=True,
        )
        login_response_text = await login_response.text()
        self.log(f"LOGIN RESPONSE STATUS: {login_response.status}")

        if "Przekroczono maksymalną liczbę logowań." in login_response_text:
            self.log("Too many login attempts")
            raise Exception("Too many login attempts")
        # If we're still on the Keycloak login page, credentials were rejected.
        if 'id="kc-form-login"' in login_response_text:
            self.log("Invalid credentials")
            raise ConfigEntryAuthFailed("Invalid credentials")
        if (self._username not in login_response_text and
                self._username.upper() not in login_response_text.upper()):
            self.log("Failed to login - username not found in response")
            raise Exception("Failed to login")

        await self.store_session(session, service)
        _LOGGER.info(f"[{self._meter_id}] Authenticated successfully via Keycloak OIDC")
        return session, login_response_text

    async def try_restore_session(self, service: str) -> (bool, str | None, ClientSession):
        session = async_create_clientsession(self._hass)
        if self._storage_key is None or self._hass is None:
            self.log("NO SESSION TO RESTORE ({service})")
            return False, None, session
        self.log(f"RESTORING SESSION {self._storage_key}_{slugify(service)}")
        store = Store(self._hass, STORAGE_VERSION, f"{self._storage_key}_{slugify(service)}")
        stored_data = await store.async_load()
        if stored_data is None:
            return False, None, session
        cookies = {k: v for k, v in stored_data.get("cookies", {}).items() if k in ["PHPSESSID", "ASP.NET_SessionId"]}
        self.log(f"COOKIES ({service}): {cookies}")
        session.cookie_jar.clear(lambda x: True)
        session.cookie_jar.update_cookies(cookies)

        success, response = await self.validate_session(session, service)
        self.log(f"SESSION VALID ({service}): {success}")

        if success:
            session_to_return = session
        else:
            self.log(f"FAILED TO RESTORE SESSION ({service})")
            self.log(f"INVALID SESSION RESPONSE ({service})")
            self.log(response)
            await store.async_save({})
            session_to_return = async_create_clientsession(self._hass)
        return success, response, session_to_return

    async def store_session(self, session: ClientSession, service: str) -> None:
        if self._storage_key is None or self._hass is None:
            self.log(f"SKIPPING STORING SESSION")
            return
        self.log(f"SAVING SESSION {self._storage_key}_{slugify(service)}")
        store = Store(self._hass, STORAGE_VERSION, f"{self._storage_key}_{slugify(service)}")
        cookies = {cookie.key: cookie.value for cookie in session.cookie_jar if cookie.key in ["PHPSESSID", "ASP.NET_SessionId"]}
        self.log(f"SAVED COOKIES ({service}) {cookies}")
        await store.async_save({"cookies": cookies})

    async def validate_session(self, session: ClientSession, service: str) -> (bool, str):
        try:
            response = await session.get(service)
            response_text = await response.text()
            return self._username in response_text or self._username.upper() in response_text.upper(), response_text
        except (ClientOSError, ServerDisconnectedError, ClientError) as err:
            self.log(f"Session validation error ({err})")
            return False, ""

    async def login(self):
        session, login_response_text = await self.login_service(CONST_URL_LOGIN, CONST_URL_SERVICE)
        self._session = session
        self.log("Logged in to eLicznik.")
        self.meters = self._get_meters(login_response_text)
        payload_select_meter = {"site[client]": self._meter_id}
        selected_meter_info = list(filter(lambda m: m["meter_id"] == self._meter_id, self.meters))
        if len(selected_meter_info) > 0:
            self._is_business = selected_meter_info[0]["meter_type"] == "WO"
        else:
            self._is_business = False
        self.log(f"Selecting meter: {self._meter_id}")
        select_response = None
        for attempt in range(2):
            try:
                select_response = await self._session.request(
                    "POST", CONST_URL_SELECT_METER, data=payload_select_meter, headers=CONST_REQUEST_HEADERS
                )
                break
            except (ClientOSError, ServerDisconnectedError) as err:
                if attempt == 0:
                    self.log(f"Transient connection error ({err}) on select meter, retrying once...")
                    await asyncio.sleep(1)
                    continue
                raise
        select_response_text = await select_response.text()
        tariff_search = re.findall(r"[^_]Tariff: '(.*)',", select_response_text)
        if len(tariff_search) > 0:
            tariff = tariff_search[0]
            return tariff
        return "unknown"

    def clear_cache(self) -> None:
        self._cache.clear()
        self._cycle_cache.clear()

    async def async_save_cache(self) -> None:
        await self._cache.async_save()

    async def async_clear_cache(self) -> None:
        self.clear_cache()
        await self._cache.async_save()

    def is_day_cached(self, day: datetime.date | datetime.datetime) -> bool:
        has_consumption = self._cache.get_value(day, generation=False) is not None
        if self._show_generation or self._show_balanced:
            has_generation = self._cache.get_value(day, generation=True) is not None
            return has_consumption and has_generation
        return has_consumption

    @staticmethod
    def _get_meters(text: str) -> list:
        regex = r".*data-data='{\"type\": \".*\"}'>.*"
        matches = list(re.finditer(regex, text))
        meters = []
        for match in matches:
            m1 = re.match(r".*value=\"([\d\_]+)\".*", match.group())
            m2 = re.match(r".*\"}'>(.*)</option>", match.group())
            m3 = re.match(r".*data-data='{\"type\": \"(.*)\"}'>.*", match.group())
            if m1 is None or m2 is None or m3 is None:
                continue
            meter_id = m1.groups()[0]
            display_name = m2.groups()[0]
            meter_type = m3.groups()[0]
            meters.append({"meter_id": meter_id, "meter_name": display_name, "meter_type": meter_type})
        return meters

    async def get_values_yearly(self, generation):
        now = datetime.datetime.now()
        first_day_of_year = now.replace(day=1, month=1)
        last_day_of_year = now.replace(day=31, month=12)
        payload = {
            "from": TauronAmiplusConnector.format_date(first_day_of_year),
            "to": TauronAmiplusConnector.format_date(last_day_of_year),
            "profile": "year",
            "type": "oze" if generation else "consum",
            "energy": 2 if generation else 1,
        }
        self.log(f"Downloading yearly data for year: {now.year}, generation: {generation}")
        values = await self.get_chart_values(payload)
        if values is not None:
            self.log(f"Downloaded yearly data for year: {now.year}, generation: {generation}")
        else:
            self.log(f"Failed to download yearly data for year: {now.year}, generation: {generation}")
        return values

    async def get_values_monthly(self, generation):
        now = datetime.datetime.now()
        month = now.month
        first_day_of_month = now.replace(day=1)
        last_day_of_month = (first_day_of_month + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)

        payload = {
            "from": TauronAmiplusConnector.format_date(first_day_of_month),
            "to": TauronAmiplusConnector.format_date(last_day_of_month),
            "profile": "month",
            "type": "oze" if generation else "consum",
            "energy": 2 if generation else 1,
        }
        values = await self.get_chart_values(payload)
        if values is not None:
            self.log(f"Downloaded monthly data for month: {now.year}.{now.month}, generation: {generation}")
        else:
            self.log(f"Failed to download monthly data for month: {now.year}.{now.month}, generation: {generation}")
        return values

    async def get_values_daily(self, generation):
        offset = 1
        data = None
        day = None
        while offset <= CONST_MAX_LOOKUP_RANGE and data is None:
            data, day = await self.get_raw_values_daily(offset, generation)
            offset += 1
        return data, day

    async def get_raw_values_daily(self, days_before, generation):
        warsaw_tz = get_time_zone("Europe/Warsaw")
        day = (datetime.datetime.now(warsaw_tz) - datetime.timedelta(days_before)).date()
        return await self.get_raw_values_daily_for_day(day, generation), TauronAmiplusConnector.format_date(day)

    async def get_values_month_hourly(self, generation):
        warsaw_tz = get_time_zone("Europe/Warsaw")
        now = datetime.datetime.now(warsaw_tz).date()
        start_day = now.replace(day=1)
        return await self.get_raw_values_daily_for_range(start_day, now, generation)

    async def get_values_year_hourly(self, generation):
        warsaw_tz = get_time_zone("Europe/Warsaw")
        now = datetime.datetime.now(warsaw_tz).date()
        start_day = now.replace(day=1, month=1)
        return await self.get_raw_values_daily_for_range(start_day, now, generation)

    async def get_values_last_30_days_hourly(self, generation):
        warsaw_tz = get_time_zone("Europe/Warsaw")
        now = datetime.datetime.now(warsaw_tz).date()
        start_day = now - datetime.timedelta(days=30)
        return await self.get_raw_values_daily_for_range(start_day, now, generation)

    async def get_values_12_months_hourly(self, generation):
        warsaw_tz = get_time_zone("Europe/Warsaw")
        now = datetime.datetime.now(warsaw_tz).date()
        start_day = now.replace(year=now.year - 1)
        return await self.get_raw_values_daily_for_range(start_day, now, generation)

    async def get_raw_values_daily_for_range(
        self, day_from: datetime.date | datetime.datetime, day_to: datetime.date | datetime.datetime, generation: bool, only_complete_days: bool = False
    ):
        if isinstance(day_from, datetime.datetime):
            day_from = day_from.date()
        if isinstance(day_to, datetime.datetime):
            day_to = day_to.date()
        data = {"data": {
            "allData": [],
            "sum": 0,
            "zones": {},
            "zonesName": {}
        }}
        for day in [day_from + datetime.timedelta(days=x) for x in range((day_to - day_from).days + 1)]:
            day_data = await self.get_raw_values_daily_for_day(day, generation)
            if day_data is not None:
                day_all_data = day_data["data"].get("allData", [])
                expected_hours = self.get_expected_hours_for_day(day)
                if only_complete_days:
                    if len(day_all_data) != expected_hours or not all(self.contains_data(a) for a in day_all_data):
                        self.log(f"Skipping incomplete day {day} from range ({len(day_all_data)}/{expected_hours} hours)")
                        continue

                data["data"]["allData"].extend(day_all_data)
                data["data"]["sum"] += day_data["data"]["sum"]
                data["data"]["zonesName"] = {**(day_data["data"]["zonesName"]), **(data["data"]["zonesName"])}
                if "tariff" in day_data["data"]:
                    data["data"]["tariff"] = day_data["data"]["tariff"]
                for z, v in day_data["data"]["zones"].items():
                    if z in data["data"]["zones"]:
                        data["data"]["zones"][z] += v
                    else:
                        data["data"]["zones"][z] = v

        if len(data["data"]["allData"]) == 0:
            return None
        return data

    async def get_raw_values_daily_for_day(self, day: datetime.date | datetime.datetime, generation: bool):
        if isinstance(day, datetime.datetime):
            day = day.date()
        day_str = TauronAmiplusConnector.format_date(day)
        expected_hours = self.get_expected_hours_for_day(day)
        cached_data = self._cache.get_value(day, generation)
        if cached_data is not None:
            self.normalize_daily_data(cached_data, day)
            self._cycle_cache_hits += 1
            self.log(f"Cache hit for day {day_str}, generation: {generation}")
            return cached_data

        cache_key = (day_str, generation)
        if cache_key in self._cycle_cache:
            self._cycle_cache_hits += 1
            self.log(f"Cycle cache hit for day {day_str}, generation: {generation}")
            cycle_data = self._cycle_cache[cache_key]
            return copy.deepcopy(cycle_data) if cycle_data is not None else None

        self._cycle_downloads += 1
        payload = {
            "from": day_str,
            "to": day_str,
            "profile": "full time",
            "type": "oze" if generation else "consum",
            "energy": 2 if generation else 1,
        }
        self.log(f"Downloading daily data for day: {day_str}, generation: {generation}")
        values = await self.get_chart_values(payload)
        if values is not None:
            if values["data"].get("allData") is None or any(
                a is None or not self.contains_data(a) for a in values["data"]["allData"]
            ):
                self.add_all_data(values, day)
                self.log(f"Replaced allData: {values}")
            else:
                for i, v in enumerate(values["data"]["allData"]):
                    v["Date"] = day.strftime("%Y-%m-%d")
                self.normalize_daily_data(values, day)

            warsaw_tz = get_time_zone("Europe/Warsaw")
            today = datetime.datetime.now(warsaw_tz).date()
            all_data = values["data"].get("allData", [])
            if (
                day < today
                and len(all_data) == expected_hours
                and all(self.contains_data(a) for a in all_data)
            ):
                self._cache.add_value(day, generation, values)

            values["data"]["allData"] = [
                d for d in values["data"]["allData"] if self.contains_data(d)
            ]
            self._cycle_cache[cache_key] = copy.deepcopy(values)
            self.log(f"Downloaded daily data for day: {day_str}, generation: {generation}")
            return values
        self._cycle_cache[cache_key] = None
        self.log(f"Failed to download daily data for day: {day_str}, generation: {generation}")
        return None

    async def get_reading(self, generation):
        date_to = datetime.datetime.now()
        date_from = (date_to - datetime.timedelta(CONST_MAX_LOOKUP_RANGE))

        date_to_str = TauronAmiplusConnector.format_date(date_to)
        payload = {
            "from": TauronAmiplusConnector.format_date(date_from),
            "to": date_to_str,
            "type": "energia-oddana" if generation else "energia-pobrana"
        }
        self.log(f"Downloading readings for date: {date_to_str}, generation: {generation}")
        post = await self.execute_post(CONST_URL_READINGS, payload)
        if post is not None:
            self.log(f"Downloaded readings for date: {date_to_str}, generation: {generation}")
            if "data" in post and len(post["data"]) > 0:
                reading = post["data"][-1]
                c_val = reading.get("C")
                r_date = reading.get("Date")
                _LOGGER.info(
                    f"[{self._meter_id}] Latest meter reading ({'generation' if generation else 'consumption'}): "
                    f"{c_val} kWh (recorded at {r_date})"
                )
        else:
            self.log(f"Failed to download readings for date: {date_to_str}, generation: {generation}")
        return post

    async def get_chart_values(self, payload):
        return await self.execute_post(CONST_URL_ENERGY_BUSINESS if self._is_business else CONST_URL_ENERGY, payload)

    async def execute_post(self, url: str, payload: dict):
        self.log(f"EXECUTING: {url} with payload: {payload}")
        response = None
        for attempt in range(2):
            try:
                response = await self._session.request(
                    "POST",
                    url,
                    data=payload,
                    headers=CONST_REQUEST_HEADERS,
                )
                break
            except (ClientOSError, ServerDisconnectedError) as err:
                if attempt == 0:
                    self.log(f"Transient connection error ({err}) on POST {url}, retrying once...")
                    await asyncio.sleep(1)
                    continue
                raise
        response_text = await response.text()
        self.log(f"RESPONSE: {response_text}")
        if "Przekroczono maksymalną liczbę logowań." in response_text:
            self.log("Too many login attempts")
            raise Exception("Too many login attempts")
        if response.status == 200 and response_text.startswith('{"success":true'):
            json_data = await response.json()
            self.log(f"RESPONSE JSON: {json_data}")
            return json_data
        return None

    def log(self, msg):
        _LOGGER.debug(f"[{self._meter_id}]: {msg}")

    async def get_moj_tauron(self) -> list[MojTauronPaymentData]:
        session, response_text = await self.login_service(CONST_URL_LOGIN_MOJ_TAURON, CONST_URL_SERVICE_MOJ_TAURON)
        self.log("MÓJ TAURON")
        self.log(response_text)
        if response_text is None:
            return []
        try:
            # parser = BeautifulSoup(response_text, "html.parser")
            # amounts = parser.select(".amount:not(.okay):not(.warning)")
            # dates = parser.select(".date:not(.okay):not(.warning)")
            payments = []
            # for i in range(min(len(amounts), len(dates))):
            #     try:
            #         amount = float(amounts[i].text.strip().split("\n")[0].strip().replace(",", ".").replace(" zł", ""))
            #         date = dates[i].text.replace("Termin:", "").strip()
            #         payments.append(MojTauronPaymentData(amount, date))
            #     except Exception as err:
            #         _LOGGER.error("Error during parsing. %s", err)
            return payments
        except Exception as err:
            _LOGGER.error("Error during downloading. %s", err)
            return []

    @staticmethod
    def format_date(date):
        return date.strftime(CONST_DATE_FORMAT)

    @staticmethod
    async def get_available_meters(username, password, hass: HomeAssistant):
        connector = TauronAmiplusConnector(username, password, "placeholder", hass)
        await connector.login()
        if connector.meters is not None and len(connector.meters) > 0:
            return connector.meters
        raise Exception("Failed to retrieve energy meters")

    @staticmethod
    async def calculate_tariff(username, password, meter_id, hass: HomeAssistant):
        connector = TauronAmiplusConnector(username, password, meter_id, hass)
        tariff = await connector.login()
        if tariff is not None:
            return tariff
        raise Exception("Failed to calculate configuration")

    @staticmethod
    def get_expected_hours_for_day(date: datetime.date | datetime.datetime) -> int:
        if isinstance(date, datetime.datetime):
            date = date.date()
        zone = get_time_zone("Europe/Warsaw")
        start = datetime.datetime.combine(date, datetime.time(0, 0), tzinfo=zone)
        end = datetime.datetime.combine(date + datetime.timedelta(days=1), datetime.time(0, 0), tzinfo=zone)
        return int((as_utc(end) - as_utc(start)).total_seconds() // 3600)

    @staticmethod
    def normalize_daily_data(data: dict, date: datetime.date | datetime.datetime) -> None:
        """Ensure allData has the expected number of hours for date (e.g. 25 for autumn DST, 23 for spring DST)."""
        if "data" not in data or "allData" not in data["data"]:
            return
        if isinstance(date, datetime.datetime):
            date = date.date()
        all_data = data["data"]["allData"]
        expected_hours = TauronAmiplusConnector.get_expected_hours_for_day(date)

        # Autumn DST: 25 hours expected, 24 provided (index 2 contains combined 3:00 hours)
        if expected_hours == 25 and len(all_data) == 24:
            h3 = all_data[2]
            try:
                combined_ec = float(h3["EC"])
                ec1 = round(combined_ec / 2.0, 3)
                ec2 = round(combined_ec - ec1, 3)
            except (ValueError, TypeError):
                ec1 = h3.get("EC")
                ec2 = h3.get("EC")

            entry1 = {**h3, "EC": f"{ec1}"}
            entry2 = {**h3, "EC": f"{ec2}"}
            all_data = list(all_data[:2]) + [entry1, entry2] + list(all_data[3:])

        # Spring DST: 23 hours expected, 24 provided (index 2 contains non-existent 2:00-3:00 hour)
        elif expected_hours == 23 and len(all_data) == 24:
            all_data = list(all_data[:2]) + list(all_data[3:])

        # Renumber all items sequentially 1..expected_hours.
        # This is essential on DST transition days where Tauron's raw API either repeats "Hour": 3
        # (Autumn DST, 25 hours with two 3:00 entries) or skips hour 3 (Spring DST), ensuring
        # distinct, monotonic hourly UTC timestamps without collisions, shifts, or negative deltas.
        if len(all_data) == expected_hours:
            for idx, item in enumerate(all_data, start=1):
                item["Hour"] = idx

        data["data"]["allData"] = all_data

    @staticmethod
    def add_all_data(data: dict, date: datetime.date | datetime.datetime):
        if isinstance(date, datetime.datetime):
            date = date.date()
        all_datas = []
        raw_values = data["data"].get("values", [])
        chart_zones = data["data"].get("chartZones", {})
        zones_name = data["data"].get("zonesName", {})
        zone = list(zones_name.keys())[0] if zones_name else "1"

        expected_hours = TauronAmiplusConnector.get_expected_hours_for_day(date)

        # Autumn DST: 24 raw values -> expand index 2 into two entries
        if expected_hours == 25 and len(raw_values) == 24:
            try:
                combined = float(raw_values[2])
                v1 = round(combined / 2.0, 3)
                v2 = round(combined - v1, 3)
            except (ValueError, TypeError):
                v1 = raw_values[2]
                v2 = raw_values[2]
            values = list(raw_values[:2]) + [f"{v1}", f"{v2}"] + list(raw_values[3:])
            expanded_zones = {}
            for z_k, flags in chart_zones.items():
                if len(flags) == 24:
                    expanded_zones[z_k] = list(flags[:2]) + [flags[2], flags[2]] + list(flags[3:])
                else:
                    expanded_zones[z_k] = flags
            chart_zones = expanded_zones
        # Spring DST: 24 raw values -> remove index 2
        elif expected_hours == 23 and len(raw_values) == 24:
            values = list(raw_values[:2]) + list(raw_values[3:])
            expanded_zones = {}
            for z_k, flags in chart_zones.items():
                if len(flags) == 24:
                    expanded_zones[z_k] = list(flags[:2]) + list(flags[3:])
                else:
                    expanded_zones[z_k] = flags
            chart_zones = expanded_zones
        else:
            values = list(raw_values)

        for i, v in enumerate(values):
            if len(zones_name) > 0 and chart_zones:
                selected_zones = [
                    z for z, flags in chart_zones.items()
                    if i < len(flags) and flags[i]
                ]
                if selected_zones:
                    zone = selected_zones[0]
            all_datas.append({
                "EC": v,
                "Date": date.strftime("%Y-%m-%d"),
                "Hour": i + 1,
                "Zone": zone,
                "Status": "0"
            })

        data["data"]["allData"] = all_datas

    @staticmethod
    def contains_data(hourly_entry: dict[str, Any]) -> bool:
        return hourly_entry.get("Status") is not None and hourly_entry.get("EC") is not None


class DailyDataCache:

    def __init__(
        self,
        meter_id: str,
        hass: HomeAssistant | None = None,
        storage_key: str | None = None,
    ):
        self._consumption_data: dict[str, Any] = dict()
        self._generation_data: dict[str, Any] = dict()
        self._meter_id = meter_id
        self._hass = hass
        self._storage_key = storage_key
        self._store = (
            Store(hass, STORAGE_VERSION, f"{storage_key}_daily_cache")
            if hass is not None and storage_key is not None
            else None
        )
        self._loaded = False
        self._dirty = False

    @staticmethod
    def _get_cache_stats(data: dict) -> tuple[int, str, str, float]:
        cons = data.get("consumption", {})
        gen = data.get("generation", {})
        all_dates = sorted(set(cons.keys()) | set(gen.keys()))
        count = len(all_dates)
        min_date = all_dates[0] if all_dates else "none"
        max_date = all_dates[-1] if all_dates else "none"
        size_kb = len(json.dumps(data)) / 1024.0
        return count, min_date, max_date, size_kb

    async def async_load(self) -> None:
        if self._loaded or self._store is None:
            return
        stored = await self._store.async_load()
        if stored:
            self._consumption_data = stored.get("consumption", {})
            self._generation_data = stored.get("generation", {})
            count, min_date, max_date, size_kb = self._get_cache_stats(stored)
            _LOGGER.info(
                f"[{self._meter_id}] Cache loaded from .storage/{self._storage_key}_daily_cache: "
                f"{count} days cached (range: {min_date} to {max_date}, size: {size_kb:.1f} KB)"
            )
        else:
            _LOGGER.info(
                f"[{self._meter_id}] No existing cache file found in .storage. A new persistent cache will be initialized."
            )
        self._loaded = True

    async def async_save(self) -> None:
        if not self._dirty or self._store is None:
            return
        data = {
            "consumption": self._consumption_data,
            "generation": self._generation_data,
        }
        await self._store.async_save(data)
        self._dirty = False
        count, min_date, max_date, size_kb = self._get_cache_stats(data)
        _LOGGER.info(
            f"[{self._meter_id}] Cache saved to .storage: "
            f"{count} total days cached (range: {min_date} to {max_date}, size: {size_kb:.1f} KB)"
        )

    def __contains__(self, item: Tuple[str, bool]):
        date_str, generation = item
        if generation:
            return date_str in self._generation_data
        return date_str in self._consumption_data

    def add_value(self, date: datetime.datetime | datetime.date, generation: bool, value):
        date_str = self._format_date(date)
        if value is None:
            return
        if generation:
            self._generation_data[date_str] = value
        else:
            self._consumption_data[date_str] = value
        self._dirty = True

    def get_value(self, date: datetime.datetime | datetime.date, generation: bool):
        date_str = self._format_date(date)
        if (date_str, generation) in self:
            if generation:
                return self._generation_data[date_str]
            return self._consumption_data[date_str]
        return None

    def delete_older_than(self, cutoff_date: datetime.datetime | datetime.date):
        cutoff_str = self._format_date(cutoff_date)
        for d in list(self._consumption_data.keys()):
            if d < cutoff_str:
                self.delete_day_str(d)
        for d in list(self._generation_data.keys()):
            if d < cutoff_str:
                self.delete_day_str(d)

    def delete_day(self, date: datetime.datetime | datetime.date):
        date_str = self._format_date(date)
        self.delete_day_str(date_str)

    def delete_day_str(self, date_str: str):
        deleted = False
        if date_str in self._generation_data:
            self._generation_data.pop(date_str)
            deleted = True
        if date_str in self._consumption_data:
            self._consumption_data.pop(date_str)
            deleted = True
        if deleted:
            self._dirty = True
            self.log(f"Deleting data from cache for day: {date_str}")

    def clear(self) -> None:
        self.log(
            f"Clearing cache: consumption - {len(self._consumption_data)}, generation - {len(self._generation_data)}"
        )
        self._generation_data.clear()
        self._consumption_data.clear()
        self._dirty = True

    @staticmethod
    def _format_date(date: datetime.datetime | datetime.date):
        return date.strftime("%Y-%m-%d")

    def log(self, msg):
        _LOGGER.debug(f"[{self._meter_id}]: {msg}")
