"""Rachio Run Times — exposes lastRun, lastRunEndTime, and nextRun per zone.

This integration calls the undocumented cloud-rest.rach.io endpoint to
obtain per-zone run timestamps that the core Rachio integration does not
expose.  It coexists with the core integration; the two share only the
same API key credential.
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import RachioRunTimesCoordinator

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rachio Run Times from a config entry."""
    coordinator = RachioRunTimesCoordinator(hass, entry)

    # Perform the first refresh before setting up platforms so that entities
    # have data immediately on startup.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
