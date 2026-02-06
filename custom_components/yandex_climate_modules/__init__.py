from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import YandexIoTClient
from .const import DOMAIN, CONF_UPDATE_INTERVAL, PLATFORMS, CONF_TOKEN, CONF_DEVICE_IDS, DEFAULT_UPDATE_INTERVAL
from .coordinator import YandexClimateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    token: str = entry.data[CONF_TOKEN]
    device_ids: list[str] = entry.data.get(CONF_DEVICE_IDS, [])
    interval_s: int = entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL)

    client = YandexIoTClient(session, token)
    coordinator = YandexClimateCoordinator(hass, client, device_ids, interval_s)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
