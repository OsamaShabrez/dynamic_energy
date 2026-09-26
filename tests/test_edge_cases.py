from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.dynamic_energy.const import (
    CONF_ENERGY_ENTITY,
    CONF_ENERGY_TYPE,
    CONF_POWER_ENTITY,
    CONF_SOURCE_ID,
    ENERGY_TYPE_CUMULATIVE,
    ENERGY_TYPE_MONTHLY,
)


def make_coordinator(coordinator_factory, options=None, states=None):
    return coordinator_factory(
        options=options or {},
        states=states or {},
    )


def make_source(
    source_id,
    power_entity,
    energy_entity,
    energy_type,
    fingerprint,
):
    return {
        CONF_SOURCE_ID: source_id,
        CONF_POWER_ENTITY: power_entity,
        CONF_ENERGY_ENTITY: energy_entity,
        CONF_ENERGY_TYPE: energy_type,
        "fingerprint": fingerprint,
    }


def test_month_rollover_starts_new_month_independently(coordinator_factory):
    coordinator = make_coordinator(coordinator_factory)

    fingerprint = "plug|energy|cumulative"
    source_id = "plug"

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_CUMULATIVE,
        baseline=100.0,
        month="2026-09",
    )

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        "2026-09",
        120.0,
    ) == pytest.approx(20.0)

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_CUMULATIVE,
        baseline=120.0,
        month="2026-10",
    )

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        "2026-10",
        120.0,
    ) == pytest.approx(0.0)

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        "2026-10",
        125.0,
    ) == pytest.approx(5.0)

    assert coordinator.storage.get_monthly_value(
        fingerprint,
        source_id,
        "2026-09",
    ) == pytest.approx(20.0)


def test_monthly_source_rollover_starts_from_new_sensor_value(coordinator_factory):
    coordinator = make_coordinator(coordinator_factory)

    fingerprint = "plug|energy|monthly"
    source_id = "plug"

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_MONTHLY,
        baseline=None,
        month="2026-09",
    )

    assert coordinator._process_monthly(
        fingerprint,
        source_id,
        "2026-09",
        42.0,
    ) == pytest.approx(42.0)

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_MONTHLY,
        baseline=None,
        month="2026-10",
    )

    assert coordinator._process_monthly(
        fingerprint,
        source_id,
        "2026-10",
        3.0,
    ) == pytest.approx(3.0)

    assert coordinator._process_monthly(
        fingerprint,
        source_id,
        "2026-10",
        8.0,
    ) == pytest.approx(8.0)


def test_unavailable_power_source_is_ignored(coordinator_factory):
    coordinator = make_coordinator(
        coordinator_factory,
        states={
            "sensor.available_power": SimpleNamespace(
                state="100",
                attributes={"unit_of_measurement": "W"},
            ),
            "sensor.unavailable_power": SimpleNamespace(
                state="unavailable",
                attributes={"unit_of_measurement": "W"},
            ),
            "sensor.unknown_power": SimpleNamespace(
                state="unknown",
                attributes={"unit_of_measurement": "W"},
            ),
        },
    )

    sources = [
        make_source(
            "available",
            "sensor.available_power",
            "sensor.available_energy",
            ENERGY_TYPE_MONTHLY,
            "available|energy|monthly",
        ),
        make_source(
            "unavailable",
            "sensor.unavailable_power",
            "sensor.unavailable_energy",
            ENERGY_TYPE_MONTHLY,
            "unavailable|energy|monthly",
        ),
        make_source(
            "unknown",
            "sensor.unknown_power",
            "sensor.unknown_energy",
            ENERGY_TYPE_MONTHLY,
            "unknown|energy|monthly",
        ),
    ]

    assert coordinator._calculate_current_power(sources) == pytest.approx(100.0)


def test_missing_power_source_is_ignored(coordinator_factory):
    coordinator = make_coordinator(
        coordinator_factory,
        states={
            "sensor.available_power": SimpleNamespace(
                state="75",
                attributes={"unit_of_measurement": "W"},
            ),
        },
    )

    sources = [
        make_source(
            "available",
            "sensor.available_power",
            "sensor.available_energy",
            ENERGY_TYPE_MONTHLY,
            "available|energy|monthly",
        ),
        make_source(
            "missing",
            "sensor.missing_power",
            "sensor.missing_energy",
            ENERGY_TYPE_MONTHLY,
            "missing|energy|monthly",
        ),
    ]

    assert coordinator._calculate_current_power(sources) == pytest.approx(75.0)


def test_multiple_sources_are_summed(coordinator_factory):
    coordinator = make_coordinator(
        coordinator_factory,
        states={
            "sensor.one_power": SimpleNamespace(
                state="100",
                attributes={"unit_of_measurement": "W"},
            ),
            "sensor.two_power": SimpleNamespace(
                state="250",
                attributes={"unit_of_measurement": "W"},
            ),
            "sensor.three_power": SimpleNamespace(
                state="0.5",
                attributes={"unit_of_measurement": "kW"},
            ),
        },
    )

    sources = [
        make_source(
            "one",
            "sensor.one_power",
            "sensor.one_energy",
            ENERGY_TYPE_MONTHLY,
            "one|energy|monthly",
        ),
        make_source(
            "two",
            "sensor.two_power",
            "sensor.two_energy",
            ENERGY_TYPE_MONTHLY,
            "two|energy|monthly",
        ),
        make_source(
            "three",
            "sensor.three_power",
            "sensor.three_energy",
            ENERGY_TYPE_MONTHLY,
            "three|energy|monthly",
        ),
    ]

    assert coordinator._calculate_current_power(sources) == pytest.approx(850.0)


def test_removed_source_is_removed_from_ranking_history(
    coordinator_factory,
    source,
):
    coordinator = make_coordinator(
        coordinator_factory,
        states={
            "sensor.a_power": SimpleNamespace(
                state="100",
                attributes={"unit_of_measurement": "W"},
            ),
        },
    )

    sources = [
        source("a"),
    ]

    coordinator._update_ranking(sources)

    assert "a" in coordinator._power_history

    coordinator._update_ranking([])

    assert "a" not in coordinator._power_history


def test_readding_source_starts_new_ranking_history(
    coordinator_factory,
    source,
):
    coordinator = make_coordinator(
        coordinator_factory,
        states={
            "sensor.a_power": SimpleNamespace(
                state="100",
                attributes={"unit_of_measurement": "W"},
            ),
        },
    )

    sources = [
        source("a"),
    ]

    coordinator._update_ranking(sources)

    assert len(coordinator._power_history["a"]) == 1

    coordinator._update_ranking([])

    assert "a" not in coordinator._power_history

    coordinator._update_ranking(sources)

    assert len(coordinator._power_history["a"]) == 1
