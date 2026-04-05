"""DataUpdateCoordinator for Rachio Run Times.

Fetches per-zone run timestamps from the undocumented cloud-rest.rach.io
endpoint.  One coordinator instance is created per config entry (i.e. per
Rachio account).

Data shape returned by _async_update_data():

    {
        "<zone_id>": {
            "zone_name":   "Front Lawn",
            "device_name": "Rachio Controller",
            "lastRun":     "2026-04-05T03:39:18Z",   # may be None
            "lastRunEndTime": "2026-04-05T05:11:06Z", # may be None
            "nextRun":     "2026-04-06T03:39:16Z",   # may be None
        },
        ...
    }
"""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_KEY,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    KEY_DEVICE_NAME,
    KEY_LAST_RUN,
    KEY_LAST_RUN_END,
    KEY_NEXT_RUN,
    KEY_ZONE_NAME,
    RACHIO_API_BASE,
    RACHIO_CLOUD_REST_BASE,
)

_LOGGER = logging.getLogger(__name__)


class RachioRunTimesCoordinator(DataUpdateCoordinator):
    """Coordinator that polls cloud-rest.rach.io for zone run timestamps."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )
        self._api_key: str = entry.data[CONF_API_KEY]
        self._person_id: str = entry.data["person_id"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _auth_headers(self) -> dict[str, str]:
        """Return the Authorization header dict used for all Rachio calls."""
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _async_get_json(self, url: str) -> dict | list:
        """Perform a GET request and return parsed JSON.

        Raises UpdateFailed on any network or HTTP error so the coordinator
        can handle retry logic consistently.
        """
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                url,
                headers=self._auth_headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 429:
                    raise UpdateFailed(
                        f"Rachio API rate limit exceeded (429) fetching {url}"
                    )
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientResponseError as err:
            raise UpdateFailed(
                f"HTTP {err.status} error fetching {url}: {err.message}"
            ) from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error fetching {url}: {err}") from err

    # ------------------------------------------------------------------
    # Step 1 — Enumerate devices and zones from the public API
    # ------------------------------------------------------------------

    async def _async_get_devices(self) -> list[dict]:
        """Return the list of irrigation controller devices for this account."""
        data = await self._async_get_json(
            f"{RACHIO_API_BASE}/person/{self._person_id}"
        )
        return data.get("devices", [])

    # ------------------------------------------------------------------
    # Step 2 — Fetch zone state from cloud-rest for each device
    # ------------------------------------------------------------------

    async def _async_get_device_state(self, device_id: str) -> dict:
        """Return the raw getDeviceState payload for one controller.

        The endpoint returns a structure like:
            {
              "state": {
                "reported": {
                  "zones": {
                    "<zone_id>": {
                      "lastRun":        "2026-04-05T03:39:18Z",
                      "lastRunEndTime": "2026-04-05T05:11:06Z",
                      "nextRun":        "2026-04-06T03:39:16Z",
                      ...
                    },
                    ...
                  }
                }
              }
            }
        """
        url = f"{RACHIO_CLOUD_REST_BASE}/device/getDeviceState/{device_id}"
        return await self._async_get_json(url)

    # ------------------------------------------------------------------
    # DataUpdateCoordinator required method
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch fresh run timestamps for all zones across all devices.

        Fetches the public-API device list once, then calls getDeviceState
        for each device.  Returns a flat dict keyed by zone_id.
        """
        result: dict[str, dict] = {}

        devices = await self._async_get_devices()

        for device in devices:
            device_id: str = device.get("id", "")
            device_name: str = device.get("name", device_id)

            # Build a zone_id → zone_name lookup from the public-API response
            zone_name_map: dict[str, str] = {
                z["id"]: z.get("name", z["id"])
                for z in device.get("zones", [])
                if z.get("enabled", True)
            }

            if not zone_name_map:
                _LOGGER.debug(
                    "Device %s (%s) has no enabled zones — skipping",
                    device_name,
                    device_id,
                )
                continue

            # Fetch zone state from cloud-rest
            try:
                state_payload = await self._async_get_device_state(device_id)
                _LOGGER.debug(
                    "Raw cloud-rest payload for device %s (%s): %s",
                    device_name,
                    device_id,
                    state_payload,
                )
            except UpdateFailed as err:
                # Log and continue — don't fail the whole update just because
                # one device's cloud-rest call failed.
                _LOGGER.warning(
                    "Could not fetch state for device %s (%s): %s",
                    device_name,
                    device_id,
                    err,
                )
                continue

            # Navigate to the zones dict inside the cloud-rest payload.
            # The exact nesting path can vary; handle both known structures.
            zones_state: dict = {}
            try:
                # Primary path: state.reported.zones
                zones_state = (
                    state_payload
                    .get("state", {})
                    .get("reported", {})
                    .get("zones", {})
                )
                # Fallback path: direct zones key at root
                if not zones_state:
                    zones_state = state_payload.get("zones", {})
            except (AttributeError, TypeError):
                _LOGGER.warning(
                    "Unexpected cloud-rest payload shape for device %s — "
                    "zone state unavailable.  Raw keys: %s",
                    device_name,
                    list(state_payload.keys()) if isinstance(state_payload, dict) else type(state_payload),
                )

            _LOGGER.debug(
                "zones_state keys for device %s: %s",
                device_name,
                list(zones_state.keys()),
            )
            _LOGGER.debug(
                "zone_name_map keys for device %s: %s",
                device_name,
                list(zone_name_map.keys()),
            )

            for zone_id, zone_name in zone_name_map.items():
                zone_state = zones_state.get(zone_id, {})

                result[zone_id] = {
                    KEY_ZONE_NAME: zone_name,
                    KEY_DEVICE_NAME: device_name,
                    KEY_LAST_RUN: zone_state.get("lastRun"),
                    KEY_LAST_RUN_END: zone_state.get("lastRunEndTime"),
                    KEY_NEXT_RUN: zone_state.get("nextRun"),
                }

                _LOGGER.debug(
                    "Zone %s (%s): lastRun=%s  lastRunEndTime=%s  nextRun=%s",
                    zone_name,
                    zone_id,
                    result[zone_id][KEY_LAST_RUN],
                    result[zone_id][KEY_LAST_RUN_END],
                    result[zone_id][KEY_NEXT_RUN],
                )

        return result
