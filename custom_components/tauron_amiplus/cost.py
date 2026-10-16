"""Calculating energy cost from per-zone prices and a fixed monthly fee."""
from __future__ import annotations

import datetime
from collections.abc import Callable
from functools import lru_cache

from homeassistant.util.dt import as_utc, get_time_zone


class CostCalculationError(Exception):
    """Cost can't be calculated (e.g. a price for a tariff zone is missing)."""


@lru_cache(maxsize=64)
def hours_in_month(year: int, month: int) -> int:
    zone = get_time_zone("Europe/Warsaw")
    month_start = datetime.datetime(year, month, 1, tzinfo=zone)
    next_month_start = datetime.datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=zone)
    return round((as_utc(next_month_start) - as_utc(month_start)).total_seconds() / 3600)


class TauronAmiplusCostCalculator:
    """cost of an hour = consumption * price of the hour's tariff zone + monthly fee / hours in the month."""

    def __init__(self, prices: dict[str, float], fixed_monthly_fee: float = 0.0) -> None:
        self._prices = prices
        self._fixed_monthly_fee = fixed_monthly_fee

    def calculate(self, consumption_data: list[dict], get_time: Callable[[dict], datetime.datetime],
                  since: datetime.datetime | None = None) -> list[dict]:
        """Cost for every hour in the same shape as consumption data.

        Hours up to and including `since` are left out, because they are already stored and won't be rewritten.
        """
        result = []
        for entry in consumption_data:
            start = get_time(entry)
            if since is not None and start <= since:
                continue
            zone = str(entry["Zone"])
            if zone not in self._prices:
                raise CostCalculationError(f"Missing price for tariff zone {zone}")
            cost = (float(entry["EC"]) * self._prices[zone]
                    + self._fixed_monthly_fee / hours_in_month(start.year, start.month))
            result.append({
                "EC": f"{round(cost, 4)}",
                "Date": entry["Date"],
                "Hour": entry["Hour"],
                "Zone": entry["Zone"],
            })
        return result
