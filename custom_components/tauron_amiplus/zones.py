"""Helpers for tariff zones reported by TAURON eLicznik."""
from __future__ import annotations

from .connector import TauronAmiplusRawData


def get_zones(data: TauronAmiplusRawData | None) -> dict[str, str]:
    """Return tariff zones known from the last downloaded data as {zone key: zone name}."""
    consumption = getattr(data, "consumption", None)
    hourly = getattr(consumption, "json_last_30_days_hourly", None)
    if not hourly:
        return {}
    return dict(hourly.get("data", {}).get("zonesName") or {})


