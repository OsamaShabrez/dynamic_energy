from __future__ import annotations

import pytest

from custom_components.dynamic_energy.const import (
    ENERGY_TYPE_CUMULATIVE,
    ENERGY_TYPE_MONTHLY,
)


def make_coordinator(coordinator_factory):
    return coordinator_factory()


def test_monthly_sensor_starts_at_current_value(
    coordinator_factory,
):
    coordinator = make_coordinator(coordinator_factory)

    fingerprint = "plug|energy|monthly"
    source_id = "plug"
    month = "2026-09"

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_MONTHLY,
        baseline=None,
        month=month,
    )

    value = coordinator._process_monthly(
        fingerprint,
        source_id,
        month,
        12.5,
    )

    assert value == pytest.approx(12.5)


def test_monthly_sensor_accumulates_across_reset(
    coordinator_factory,
):
    coordinator = make_coordinator(coordinator_factory)

    fingerprint = "plug|energy|monthly"
    source_id = "plug"
    month = "2026-09"

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_MONTHLY,
        baseline=None,
        month=month,
    )

    assert coordinator._process_monthly(
        fingerprint,
        source_id,
        month,
        12.5,
    ) == pytest.approx(12.5)

    assert coordinator._process_monthly(
        fingerprint,
        source_id,
        month,
        15.0,
    ) == pytest.approx(15.0)

    assert coordinator._process_monthly(
        fingerprint,
        source_id,
        month,
        2.0,
    ) == pytest.approx(17.0)

    assert coordinator._process_monthly(
        fingerprint,
        source_id,
        month,
        4.0,
    ) == pytest.approx(19.0)


def test_cumulative_sensor_starts_at_zero(
    coordinator_factory,
):
    coordinator = make_coordinator(coordinator_factory)

    fingerprint = "plug|energy|cumulative"
    source_id = "plug"
    month = "2026-09"

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_CUMULATIVE,
        baseline=100.0,
        month=month,
    )

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        100.0,
    ) == pytest.approx(0.0)


def test_cumulative_sensor_accumulates(
    coordinator_factory,
):
    coordinator = make_coordinator(coordinator_factory)

    fingerprint = "plug|energy|cumulative"
    source_id = "plug"
    month = "2026-09"

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_CUMULATIVE,
        baseline=100.0,
        month=month,
    )

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        100.0,
    ) == pytest.approx(0.0)

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        101.5,
    ) == pytest.approx(1.5)

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        105.0,
    ) == pytest.approx(5.0)


def test_cumulative_counter_reset_does_not_go_negative(
    coordinator_factory,
):
    coordinator = make_coordinator(coordinator_factory)

    fingerprint = "plug|energy|cumulative"
    source_id = "plug"
    month = "2026-09"

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_CUMULATIVE,
        baseline=100.0,
        month=month,
    )

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        100.0,
    ) == pytest.approx(0.0)

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        105.0,
    ) == pytest.approx(5.0)

    reset_value = coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        2.0,
    )

    assert reset_value == pytest.approx(5.0)
    assert reset_value >= 0.0

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        4.0,
    ) == pytest.approx(7.0)


def test_cumulative_multiple_resets_accumulate(
    coordinator_factory,
):
    coordinator = make_coordinator(coordinator_factory)

    fingerprint = "plug|energy|cumulative"
    source_id = "plug"
    month = "2026-09"

    coordinator.storage.ensure_source(
        fingerprint=fingerprint,
        source_id=source_id,
        energy_type=ENERGY_TYPE_CUMULATIVE,
        baseline=100.0,
        month=month,
    )

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        110.0,
    ) == pytest.approx(10.0)

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        5.0,
    ) == pytest.approx(10.0)

    assert coordinator._process_cumulative(
        fingerprint,
        source_id,
        month,
        8.0,
    ) == pytest.approx(13.0)
