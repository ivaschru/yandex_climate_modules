from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, INST_CO2, INST_HUMIDITY, INST_TEMPERATURE, CONF_ENABLE_LAST_UPDATED

INST_TO_META: dict[str, tuple[str, str, SensorDeviceClass | None]] = {
    INST_TEMPERATURE: ("Temperature", "°C", SensorDeviceClass.TEMPERATURE),
    INST_HUMIDITY: ("Humidity", "%", SensorDeviceClass.HUMIDITY),
    INST_CO2: ("CO2", "ppm", None),
}


@dataclass(frozen=True)
class DerivedKind:
    key: str
    name_suffix: str


DER_LAST_UPDATED = DerivedKind("last_updated", "Last Updated")


def _normalize_device_name(name: str) -> str:
    if name.strip().lower() == "умное устройство":
        return "Климатическая станция"
    return name


def _find_prop(properties: list[dict[str, Any]], instance: str) -> dict[str, Any] | None:
    for p in properties:
        st = p.get("state") or {}
        if st.get("instance") == instance:
            return p
    return None


def _last_updated_max(properties: list[dict[str, Any]]) -> float | None:
    vals: list[float] = []
    for p in properties:
        lu = p.get("last_updated")
        if isinstance(lu, (int, float)):
            vals.append(float(lu))
    return max(vals) if vals else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_ids: list[str] = entry.data.get("device_ids", [])

    enable_last = entry.options.get(CONF_ENABLE_LAST_UPDATED, True)

    entities: list[SensorEntity] = []

    for did in device_ids:
        for inst in (INST_TEMPERATURE, INST_HUMIDITY, INST_CO2):
            entities.append(YandexClimateSensor(coordinator, did, inst))

        # Diagnostic timestamp (last updated)
        if enable_last:
            entities.append(YandexClimateDerivedSensor(coordinator, did, DER_LAST_UPDATED))

    async_add_entities(entities)


class YandexClimateBase(SensorEntity):
    """Base class for all sensors in this integration."""

    _attr_should_poll = False

    def __init__(self, coordinator, device_id: str) -> None:
        self.coordinator = coordinator
        self.device_id = device_id

    @property
    def available(self) -> bool:
        return self.device_id in (self.coordinator.data or {})

    @property
    def _device_payload(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self.device_id, {})

    @property
    def device_info(self):
        base = _normalize_device_name(self._device_payload.get("name") or "Yandex Climate Module")
        room = self._device_payload.get("room_name")
        tail = self.device_id[-5:]
        name = f"{base} {room} ({tail})" if room else f"{base} ({tail})"
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": name,
            "manufacturer": "Yandex",
            "model": "Climate module (IoT API)",
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


class YandexClimateSensor(YandexClimateBase):
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        base = _normalize_device_name(self._device_payload.get("name") or "Yandex Climate Module")
        room = self._device_payload.get("room_name")
        tail = self.device_id[-5:]
        device_name = f"{base} {room} ({tail})" if room else f"{base} ({tail})"
        title, _, _ = INST_TO_META[self.instance]
        return f"{device_name} {title}"

    def __init__(self, coordinator, device_id: str, instance: str) -> None:
        super().__init__(coordinator, device_id)
        self.instance = instance

        title, unit, dev_class = INST_TO_META[instance]
        self._attr_unique_id = f"{device_id}_{instance}"
        self._attr_native_unit_of_measurement = unit
        if dev_class:
            self._attr_device_class = dev_class
        if instance == INST_CO2:
            self._attr_icon = "mdi:molecule-co2"

    @property
    def native_value(self):
        props = self._device_payload.get("properties") or []
        p = _find_prop(props, self.instance)
        if not p:
            return None
        val = (p.get("state") or {}).get("value")
        if val is None:
            return None

        if self.instance in (INST_TEMPERATURE, INST_HUMIDITY):
            return round(float(val), 1)
        if self.instance == INST_CO2:
            return int(round(float(val), 0))
        return val


class YandexClimateDerivedSensor(YandexClimateBase):
    """Diagnostic sensors derived from Yandex device properties."""

    @property
    def name(self) -> str:
        base = _normalize_device_name(self._device_payload.get("name") or "Yandex Climate Module")
        room = self._device_payload.get("room_name")
        tail = self.device_id[-5:]
        device_name = f"{base} {room} ({tail})" if room else f"{base} ({tail})"
        return f"{device_name} {self.kind.name_suffix}"

    def __init__(self, coordinator, device_id: str, kind: DerivedKind) -> None:
        super().__init__(coordinator, device_id)
        self.kind = kind
        self._attr_unique_id = f"{device_id}_{kind.key}"

        if kind.key == "last_updated":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_state_class = None
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        props = self._device_payload.get("properties") or []
        ts = _last_updated_max(props)
        if ts is None:
            return None

        if self.kind.key == "last_updated":
            return datetime.fromtimestamp(ts, tz=timezone.utc)

        return None
