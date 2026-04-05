"""Sensor platform for Rachio Run Times.

Creates three sensor entities per enabled zone:
  - sensor.rachio_<zone>_last_run          — UTC ISO timestamp of run start
  - sensor.rachio_<zone>_last_run_end      — UTC ISO timestamp of run end
  - sensor.rachio_<zone>_next_run          — UTC ISO timestamp of next scheduled run

All sensors are device_class: timestamp so HA automatically converts the
UTC ISO string to the user's local time in the UI and in automations.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import parse_datetime

from .const import (
    DOMAIN,
    KEY_DEVICE_NAME,
    KEY_LAST_RUN,
    KEY_LAST_RUN_END,
    KEY_NEXT_RUN,
    KEY_ZONE_NAME,
)
from .coordinator import RachioRunTimesCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RachioRunTimeSensorDescription(SensorEntityDescription):
    """Extend SensorEntityDescription with the coordinator data key."""

    data_key: str = ""


# One description per sensor type — applied to every zone
SENSOR_DESCRIPTIONS: tuple[RachioRunTimeSensorDescription, ...] = (
    RachioRunTimeSensorDescription(
        key="last_run",
        data_key=KEY_LAST_RUN,
        name="Last Run",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:history",
    ),
    RachioRunTimeSensorDescription(
        key="last_run_end",
        data_key=KEY_LAST_RUN_END,
        name="Last Run End",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:history",
    ),
    RachioRunTimeSensorDescription(
        key="next_run",
        data_key=KEY_NEXT_RUN,
        name="Next Run",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for every zone found by the coordinator."""
    coordinator: RachioRunTimesCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[RachioRunTimeSensor] = []
    for zone_id, zone_data in coordinator.data.items():
        for description in SENSOR_DESCRIPTIONS:
            entities.append(
                RachioRunTimeSensor(
                    coordinator=coordinator,
                    entry=entry,
                    zone_id=zone_id,
                    description=description,
                )
            )

    async_add_entities(entities)


class RachioRunTimeSensor(CoordinatorEntity[RachioRunTimesCoordinator], SensorEntity):
    """A single run-time timestamp sensor for one Rachio zone."""

    entity_description: RachioRunTimeSensorDescription

    def __init__(
        self,
        coordinator: RachioRunTimesCoordinator,
        entry: ConfigEntry,
        zone_id: str,
        description: RachioRunTimeSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._zone_id = zone_id
        self._entry_id = entry.entry_id

        zone_data = coordinator.data[zone_id]
        zone_name: str = zone_data[KEY_ZONE_NAME]
        device_name: str = zone_data[KEY_DEVICE_NAME]

        # Unique ID — stable across restarts
        self._attr_unique_id = f"{entry.entry_id}_{zone_id}_{description.key}"

        # Human-readable name shown in the UI
        self._attr_name = f"Rachio {zone_name} {description.name}"

        # Group all sensors for this zone under a single HA device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, zone_id)},
            "name": f"{device_name} — {zone_name}",
            "manufacturer": "Rachio",
            "model": "Irrigation Zone",
        }

    @property
    def _zone_data(self) -> dict:
        """Return this zone's slice of the coordinator data."""
        return self.coordinator.data.get(self._zone_id, {})

    @property
    def native_value(self):
        """Return the sensor value as a timezone-aware datetime (or None).

        HA's SensorDeviceClass.TIMESTAMP requires a datetime object — not a
        raw string.  parse_datetime() handles ISO 8601 UTC strings
        (e.g. '2026-04-05T03:39:18Z') and returns a UTC-aware datetime.
        """
        raw: str | None = self._zone_data.get(self.entity_description.data_key)
        if raw is None:
            return None
        dt = parse_datetime(raw)
        if dt is None:
            _LOGGER.warning(
                "Could not parse datetime string %r for %s", raw, self._attr_name
            )
        return dt

    @property
    def available(self) -> bool:
        """Mark unavailable if the coordinator has no data for this zone."""
        return (
            self.coordinator.last_update_success
            and self._zone_id in self.coordinator.data
        )
