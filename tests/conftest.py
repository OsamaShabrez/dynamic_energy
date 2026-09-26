from __future__ import annotations

from collections import defaultdict, deque
from unittest.mock import MagicMock

import pytest

from custom_components.dynamic_energy.coordinator import (
    DynamicEnergyCoordinator,
)


class FakeState:
    def __init__(self, state, attributes=None):
        self.state = state
        self.attributes = attributes or {}


class FakeStorage:
    def __init__(self):
        self.sources = {}
        self.month_states = {}

    def ensure_source(
        self,
        fingerprint,
        source_id,
        energy_type,
        baseline,
        month,
    ):
        key = (fingerprint, source_id, month)

        if key not in self.month_states:
            self.month_states[key] = {
                "baseline": baseline,
                "carry": 0.0,
                "last_raw": None,
                "value": 0.0,
            }

    def get_month_state(
        self,
        fingerprint,
        source_id,
        month,
    ):
        return self.month_states.get((fingerprint, source_id, month))

    def set_month_state(
        self,
        fingerprint,
        source_id,
        month,
        **values,
    ):
        key = (fingerprint, source_id, month)

        state = self.month_states.setdefault(
            key,
            {
                "baseline": None,
                "carry": 0.0,
                "last_raw": None,
                "value": 0.0,
            },
        )

        state.update(values)

    def get_monthly_value(
        self,
        fingerprint,
        source_id,
        month,
    ):
        state = self.get_month_state(
            fingerprint,
            source_id,
            month,
        )

        if state is None:
            return 0.0

        return float(state.get("value", 0.0))


@pytest.fixture
def coordinator_factory():
    def create(options=None, states=None):
        hass = MagicMock()
        hass.states = states or {}

        entry = MagicMock()
        entry.entry_id = "test-entry"
        entry.options = options or {}
        entry.data = {}

        storage = FakeStorage()

        coordinator = DynamicEnergyCoordinator.__new__(DynamicEnergyCoordinator)

        coordinator.hass = hass
        coordinator.config_entry = entry
        coordinator.storage = storage
        coordinator._power_history = defaultdict(deque)
        coordinator._displayed_ranking = []
        coordinator._challenge_counts = defaultdict(int)
        coordinator._challenge_target = None

        return coordinator

    return create


@pytest.fixture
def source():
    def make(name, power_entity=None):
        return {
            "source_id": name,
            "name": name,
            "power_entity": (power_entity or f"sensor.{name}_power"),
            "energy_entity": f"sensor.{name}_energy",
            "energy_type": "monthly",
            "icon": "mdi:power-plug",
        }

    return make
