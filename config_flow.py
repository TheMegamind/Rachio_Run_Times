"""Config flow for Rachio Run Times integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_API_KEY, DOMAIN, RACHIO_API_BASE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def _validate_api_key(hass: HomeAssistant, api_key: str) -> dict[str, str]:
    """Validate the API key by fetching the person/info endpoint.

    Returns a dict with 'person_id' and 'username' on success.
    Raises InvalidAuth on 401/403, CannotConnect on network errors.
    """
    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with session.get(
            f"{RACHIO_API_BASE}/person/info",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 401:
                raise InvalidAuth
            if resp.status == 403:
                raise InvalidAuth
            resp.raise_for_status()
            data = await resp.json()
    except aiohttp.ClientError as err:
        raise CannotConnect from err

    return {"person_id": data["id"], "username": data.get("username", "")}


class RachioRunTimesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rachio Run Times."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — API key entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _validate_api_key(self.hass, user_input[CONF_API_KEY])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating Rachio API key")
                errors["base"] = "unknown"
            else:
                # Prevent duplicate entries for the same Rachio account
                await self.async_set_unique_id(info["person_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Rachio ({info['username']})",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        "person_id": info["person_id"],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error raised when we cannot reach the Rachio API."""


class InvalidAuth(HomeAssistantError):
    """Error raised when the API key is rejected."""
