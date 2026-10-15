from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone

import pytest
from conftest import FakeState

from custom_components.dynamic_energy import coordinator as coordinator_module
from custom_components.dynamic_energy.const import (
    CONF_CHALLENGE_CONFIRMATIONS,
    CONF_CHALLENGE_THRESHOLD,
    CONF_MINIMUM_POWER,
    CONF_OBSERVATION_WINDOW,
    RANKING_METHOD_AVERAGE,
    RANKING_METHOD_PEAK,
    RANKING_METHOD_RECENT_WEIGHTED,
)


def test_initial_top_four(coordinator_factory, source):
    coordinator = coordinator_factory(
        options={
            CONF_OBSERVATION_WINDOW: 10,
            CONF_MINIMUM_POWER: 3,
            CONF_CHALLENGE_THRESHOLD: 5,
            CONF_CHALLENGE_CONFIRMATIONS: 2,
        },
        states={
            "sensor.a_power": FakeState(
                "100",
                {"unit_of_measurement": "W"},
            ),
            "sensor.b_power": FakeState(
                "80",
                {"unit_of_measurement": "W"},
            ),
            "sensor.c_power": FakeState(
                "60",
                {"unit_of_measurement": "W"},
            ),
            "sensor.d_power": FakeState(
                "40",
                {"unit_of_measurement": "W"},
            ),
            "sensor.e_power": FakeState(
                "20",
                {"unit_of_measurement": "W"},
            ),
            "sensor.f_power": FakeState(
                "10",
                {"unit_of_measurement": "W"},
            ),
        },
    )

    result = coordinator._update_ranking(
        [source(name) for name in ["a", "b", "c", "d", "e", "f"]]
    )

    assert [item["source_id"] for item in result] == ["a", "b", "c", "d"]


def test_challenger_replaces_after_required_confirmations(
    coordinator_factory,
):
    coordinator = coordinator_factory(
        options={
            CONF_CHALLENGE_THRESHOLD: 5,
            CONF_CHALLENGE_CONFIRMATIONS: 2,
        }
    )

    coordinator._displayed_ranking = [
        "a",
        "b",
        "c",
        "d",
    ]

    ordered = [
        "a",
        "b",
        "c",
        "e",
        "d",
    ]

    scores = {
        "a": 100,
        "b": 80,
        "c": 60,
        "d": 40,
        "e": 43,
    }

    current = dict(scores)

    coordinator._update_displayed_ranking(
        ordered,
        scores,
        current,
    )

    assert coordinator._displayed_ranking == [
        "a",
        "b",
        "c",
        "d",
    ]

    coordinator._update_displayed_ranking(
        ordered,
        scores,
        current,
    )

    assert coordinator._displayed_ranking == [
        "a",
        "b",
        "c",
        "e",
    ]


def test_challenger_below_threshold_does_not_replace(
    coordinator_factory,
):
    coordinator = coordinator_factory(
        options={
            CONF_CHALLENGE_THRESHOLD: 5,
            CONF_CHALLENGE_CONFIRMATIONS: 1,
        }
    )

    coordinator._displayed_ranking = [
        "a",
        "b",
        "c",
        "d",
    ]

    ordered = [
        "a",
        "b",
        "c",
        "e",
        "d",
    ]

    scores = {
        "a": 100,
        "b": 80,
        "c": 60,
        "d": 40,
        "e": 42,
    }

    coordinator._update_displayed_ranking(
        ordered,
        scores,
        dict(scores),
    )

    assert coordinator._displayed_ranking == [
        "a",
        "b",
        "c",
        "d",
    ]


def test_minimum_power_excludes_small_loads(
    coordinator_factory,
    source,
):
    coordinator = coordinator_factory(
        options={
            CONF_OBSERVATION_WINDOW: 10,
            CONF_MINIMUM_POWER: 3,
            CONF_CHALLENGE_THRESHOLD: 5,
            CONF_CHALLENGE_CONFIRMATIONS: 1,
        }
    )

    coordinator.hass.states = {
        f"sensor.{name}_power": FakeState(
            str(power),
            {"unit_of_measurement": "W"},
        )
        for name, power in {
            "a": 100,
            "b": 80,
            "c": 60,
            "d": 40,
            "e": 2,
            "f": 1,
        }.items()
    }

    result = coordinator._update_ranking(
        [
            source(name)
            for name in [
                "a",
                "b",
                "c",
                "d",
                "e",
                "f",
            ]
        ]
    )

    assert [item["source_id"] for item in result] == ["a", "b", "c", "d"]


def test_zero_minimum_power_allows_zero_watt_source(
    coordinator_factory,
    source,
):
    coordinator = coordinator_factory(
        options={
            CONF_OBSERVATION_WINDOW: 10,
            CONF_MINIMUM_POWER: 0,
        },
        states={
            "sensor.a_power": FakeState(
                "0",
                {"unit_of_measurement": "W"},
            )
        },
    )

    result = coordinator._update_ranking([source("a")])

    assert len(result) == 1
    assert result[0]["source_id"] == "a"
    assert result[0]["power"] == 0


def test_observation_window_discards_old_samples(
    coordinator_factory,
    source,
    monkeypatch,
):
    coordinator = coordinator_factory(
        options={
            CONF_OBSERVATION_WINDOW: 10,
            CONF_MINIMUM_POWER: 0,
        }
    )

    current_time = datetime(
        2026,
        9,
        25,
        12,
        0,
        tzinfo=timezone.utc,
    )

    monkeypatch.setattr(
        coordinator_module.dt_util,
        "now",
        lambda: current_time,
    )

    coordinator._power_history = {
        "a": deque(
            [
                (
                    current_time - timedelta(seconds=20),
                    100.0,
                ),
                (
                    current_time - timedelta(seconds=5),
                    50.0,
                ),
            ]
        )
    }

    coordinator.hass.states = {
        "sensor.a_power": FakeState(
            "50",
            {"unit_of_measurement": "W"},
        )
    }

    coordinator._update_ranking([source("a")])

    history = coordinator._power_history["a"]

    assert all(
        timestamp >= current_time - timedelta(seconds=10) for timestamp, _ in history
    )


def test_kw_power_is_normalized_to_watts(
    coordinator_factory,
    source,
):
    coordinator = coordinator_factory(
        options={
            CONF_OBSERVATION_WINDOW: 10,
            CONF_MINIMUM_POWER: 0,
        },
        states={
            "sensor.a_power": FakeState(
                "1.5",
                {"unit_of_measurement": "kW"},
            )
        },
    )

    result = coordinator._update_ranking([source("a")])

    assert result[0]["power"] == pytest.approx(1500.0)


def test_ranking_methods(coordinator_factory):
    from collections import deque

    from custom_components.dynamic_energy.const import (
        CONF_RANKING_METHOD,
        RANKING_METHOD_AVERAGE,
        RANKING_METHOD_PEAK,
        RANKING_METHOD_RECENT_WEIGHTED,
    )

    samples = [20.0, 60.0, 100.0]

    coordinator = coordinator_factory()

    coordinator._power_history["a"] = deque(
        (float(i), value) for i, value in enumerate(samples)
    )

    coordinator.config_entry.options = {
        CONF_RANKING_METHOD: RANKING_METHOD_AVERAGE,
    }

    average = coordinator._calculate_ranking_score("a")

    coordinator.config_entry.options = {
        CONF_RANKING_METHOD: RANKING_METHOD_RECENT_WEIGHTED,
    }

    recent = coordinator._calculate_ranking_score("a")

    coordinator.config_entry.options = {
        CONF_RANKING_METHOD: RANKING_METHOD_PEAK,
    }

    peak = coordinator._calculate_ranking_score("a")

    assert average == pytest.approx(60.0)
    assert recent == pytest.approx(73.3333333)
    assert peak == pytest.approx(100.0)
