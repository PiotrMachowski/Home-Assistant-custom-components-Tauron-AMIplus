"""Debug logs are often pasted into public GitHub issues, so they must not
contain session cookie values (they allow using the logged-in eLicznik session)."""
import asyncio
import logging

from custom_components.tauron_amiplus import connector as connector_module
from custom_components.tauron_amiplus.connector import TauronAmiplusConnector

SECRET = "s3cr3t-session-value"


class FakeCookie:
    def __init__(self, key, value):
        self.key, self.value = key, value


class FakeJar(list):
    def clear(self, predicate=None):
        super().clear()

    def update_cookies(self, cookies):
        self.extend(FakeCookie(k, v) for k, v in cookies.items())


class FakeSession:
    def __init__(self):
        self.cookie_jar = FakeJar()


class FakeStore:
    saved = {"cookies": {"PHPSESSID": SECRET}}

    def __init__(self, *args, **kwargs):
        pass

    async def async_load(self):
        return FakeStore.saved

    async def async_save(self, data):
        FakeStore.saved = data


def test_session_cookie_values_are_not_logged(monkeypatch, caplog):
    monkeypatch.setattr(connector_module, "Store", FakeStore)
    monkeypatch.setattr(connector_module, "async_create_clientsession", lambda hass: FakeSession())
    connector = TauronAmiplusConnector("user", "password", "meter", hass=object(), config_entry_id="entry")

    async def valid(session, service):
        return True, "user"

    connector.validate_session = valid
    caplog.set_level(logging.DEBUG, logger=connector_module.__name__)

    async def run():
        success, _, session = await connector.try_restore_session("https://example")
        assert success
        await connector.store_session(session, "https://example")

    asyncio.run(run())
    assert FakeStore.saved == {"cookies": {"PHPSESSID": SECRET}}
    assert "PHPSESSID" in caplog.text
    assert SECRET not in caplog.text
