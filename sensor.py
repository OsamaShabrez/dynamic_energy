from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN
from .coordinator import DynamicEnergyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DynamicEnergyCoordinator = entry.runtime_data

    async_add_entities(
        [
            DynamicEnergyCurrentPowerSensor(coordinator),
            DynamicEnergyMonthlyEnergySensor(coordinator),
        ]
    )


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


class DynamicEnergyCurrentPowerSensor(
    DynamicEnergyBaseSensor,
):
    _attr_name = "Apartment Current Power"
    _attr_unique_id = "apartment_current_power"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None

        return float(
            self.coordinator.data.get(
                "current_power",
                0.0,
            )
        )


class DynamicEnergyMonthlyEnergySensor(
    DynamicEnergyBaseSensor,
):
    _attr_name = "Apartment Energy This Month"
    _attr_unique_id = "apartment_energy_this_month"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None

        return float(
            self.coordinator.data.get(
                "monthly_energy",
                0.0,
            )
        )
