from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    MATCH_ALL,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .coordinator import DynamicEnergyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DynamicEnergyCoordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        DynamicEnergyCurrentPowerSensor(coordinator),
        DynamicEnergyMonthlyEnergySensor(coordinator),
    ]

    entities.extend(
        DynamicEnergyTopConsumerSensor(
            coordinator,
            rank=rank,
        )
        for rank in range(1, 5)
    )

    async_add_entities(entities)


class DynamicEnergyBaseSensor(
    CoordinatorEntity[DynamicEnergyCoordinator],
    SensorEntity,
):
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: DynamicEnergyCoordinator,
    ) -> None:
        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )


class DynamicEnergyMonthlyEnergySensor(DynamicEnergyBaseSensor):
    _attr_name = "Apartment Energy Month"
    _attr_unique_id = "apartment_energy_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None

        return float(self.coordinator.data.get("current_power", 0.0))


class DynamicEnergyMonthlyEnergySensor(DynamicEnergyBaseSensor):
    _attr_name = "Apartment Energy Month"
    _attr_unique_id = "apartment_energy_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None

        return float(self.coordinator.data.get("monthly_energy", 0.0))


class DynamicEnergyTopConsumerSensor(DynamicEnergyBaseSensor):
    _unrecorded_attributes = frozenset({MATCH_ALL})

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: DynamicEnergyCoordinator,
        rank: int,
    ) -> None:
        super().__init__(coordinator)

        self._rank = rank

    @property
    def name(self) -> str:
        return f"Top Consumer {self._rank}"

    @property
    def unique_id(self) -> str:
        return f"top_consumer_{self._rank}"

    @property
    def native_value(self) -> float | None:
        consumer = self._get_consumer()

        if consumer is None:
            return 0.0

        return float(consumer.get("power", 0.0))

    @property
    def icon(self) -> str:
        consumer = self._get_consumer()

        if consumer is None:
            return "mdi:flash"

        return consumer.get("icon") or "mdi:flash"

    @property
    def extra_state_attributes(self) -> dict:
        consumer = self._get_consumer()

        if consumer is None:
            return {
                "rank": self._rank,
                "name": None,
                "power": 0.0,
                "source_id": None,
                "icon": "mdi:flash",
            }

        return {
            "rank": self._rank,
            "name": consumer.get("name"),
            "power": float(consumer.get("power", 0.0)),
            "source_id": consumer.get("source_id"),
            "icon": consumer.get("icon") or "mdi:flash",
        }

    def _get_consumer(self) -> dict | None:
        if self.coordinator.data is None:
            return None

        top_sources = self.coordinator.data.get("top_sources", [])

        index = self._rank - 1

        if index >= len(top_sources):
            return None

        consumer = top_sources[index]

        if not isinstance(consumer, dict):
            return None

        return consumer
