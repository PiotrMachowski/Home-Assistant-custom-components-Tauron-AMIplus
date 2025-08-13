from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import TauronAmiplusUpdateCoordinator


@dataclass
class TauronAmiplusRuntimeData:
    coordinator: TauronAmiplusUpdateCoordinator


type TauronAmiplusConfigEntry = ConfigEntry[TauronAmiplusRuntimeData]
