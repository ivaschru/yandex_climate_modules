from __future__ import annotations

from typing import Any

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    YandexIoTClient,
    YandexIoTApiError,
    YandexIoTAuthError,
    YandexIoTPermissionError,
)
from .const import DOMAIN, CONF_TOKEN, CONF_DEVICE_IDS, CLIMATE_INSTANCES

_LOGGER = logging.getLogger(__name__)


def _is_climate_module(device: dict[str, Any]) -> bool:
    props = device.get("properties") or []
    instances: set[str] = set()
    for p in props:
        st = p.get("state") or {}
        inst = st.get("instance")
        if inst:
            instances.add(inst)
    # strict match (all 3) to avoid false positives
    return CLIMATE_INSTANCES.issubset(instances)


class YandexClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            token = (user_input[CONF_TOKEN] or "").strip()
            if token.lower().startswith("bearer "):
                token = token.split(None, 1)[1].strip()
            session = async_get_clientsession(self.hass)
            client = YandexIoTClient(session, token)
            try:
                await client.validate_token()
                device_ids = await client.list_device_ids()
                # Fetch each device details to find climate modules
                devices = []
                for did in device_ids:
                    try:
                        dev = await client.get_device(did)
                        devices.append({"id": dev.id, "name": dev.name, "properties": dev.properties})
                    except Exception as e:  # noqa: BLE001
                        _LOGGER.debug("Failed to fetch device %s: %s", did, e)
                climate = [d for d in devices if _is_climate_module(d)]
                if not climate:
                    errors["base"] = "no_modules_found"
                else:
                    self._token = token
                    self._climate_list = climate
                    return await self.async_step_select_modules()
            except YandexIoTAuthError as e:
                _LOGGER.debug("Token validation failed (401): %s", e)
                errors["base"] = "auth_401"
            except YandexIoTPermissionError as e:
                _LOGGER.debug("Token missing permissions (403): %s", e)
                errors["base"] = "auth_403"
            except YandexIoTApiError as e:
                _LOGGER.debug("Yandex IoT API error: %s", e)
                errors["base"] = "api_error"
            except Exception as e:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during config flow: %s", e)
                errors["base"] = "unknown"

        schema = vol.Schema({vol.Required(CONF_TOKEN): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select_modules(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        climate = getattr(self, "_climate_list", [])
        if not climate:
            return self.async_abort(reason="no_modules_found")

        options = {d["id"]: f"{d.get('name','Модуль')} ({d['id'][:8]}...)" for d in climate}

        if user_input is not None:
            device_ids = user_input[CONF_DEVICE_IDS]
            if not device_ids:
                errors["base"] = "select_at_least_one"
            else:
                return self.async_create_entry(
                    title="Yandex Climate Modules",
                    data={
                        CONF_TOKEN: getattr(self, "_token"),
                        CONF_DEVICE_IDS: list(device_ids),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_IDS): vol.All(
                    list,
                    [vol.In(options)],
                )
            }
        )
        return self.async_show_form(step_id="select_modules", data_schema=schema, errors=errors)
