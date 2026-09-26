from __future__ import annotations

from types import SimpleNamespace

from custom_components.dynamic_energy.sensor import (
    DynamicEnergyCurrentPowerSensor,
    DynamicEnergyMonthlyEnergySensor,
)


def make_sensor(sensor_class, coordinator):
    return sensor_class(coordinator)


def test_current_power_sensor_unique_id():
    sensor = make_sensor(
        DynamicEnergyCurrentPowerSensor,
        SimpleNamespace(
            data={"current_power": 0.0},
            last_update_success=True,
        ),
    )

    assert sensor.unique_id == "apartment_current_power"


def test_monthly_energy_sensor_unique_id():
    sensor = make_sensor(
        DynamicEnergyMonthlyEnergySensor,
        SimpleNamespace(
            data={"monthly_energy": 0.0},
            last_update_success=True,
        ),
    )

    assert sensor.unique_id == "apartment_energy_month"


def test_current_power_sensor_value():
    coordinator = SimpleNamespace(
        data={
            "current_power": 1047.0,
        },
        last_update_success=True,
    )

    sensor = make_sensor(
        DynamicEnergyCurrentPowerSensor,
        coordinator,
    )

    assert sensor.native_value == 1047.0


def test_monthly_energy_sensor_value():
    coordinator = SimpleNamespace(
        data={
            "monthly_energy": 18.75,
        },
        last_update_success=True,
    )

    sensor = make_sensor(
        DynamicEnergyMonthlyEnergySensor,
        coordinator,
    )

    assert sensor.native_value == 18.75
    assert sensor.available is True


def test_sensors_unavailable_without_coordinator_data():
    coordinator = SimpleNamespace(
        data=None,
        last_update_success=True,
    )

    power_sensor = make_sensor(
        DynamicEnergyCurrentPowerSensor,
        coordinator,
    )

    energy_sensor = make_sensor(
        DynamicEnergyMonthlyEnergySensor,
        coordinator,
    )

    assert power_sensor.native_value is None
    assert energy_sensor.native_value is None
    assert power_sensor.available is False
    assert energy_sensor.available is False


def test_sensors_unavailable_when_coordinator_update_failed():
    coordinator = SimpleNamespace(
        data={
            "current_power": 100.0,
            "monthly_energy": 10.0,
        },
        last_update_success=False,
    )

    power_sensor = make_sensor(
        DynamicEnergyCurrentPowerSensor,
        coordinator,
    )

    energy_sensor = make_sensor(
        DynamicEnergyMonthlyEnergySensor,
        coordinator,
    )

    assert power_sensor.available is False
    assert energy_sensor.available is False
