from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CHALLENGE_CONFIRMATIONS,
    CONF_CHALLENGE_THRESHOLD,
    CONF_ENERGY_ENTITY,
    CONF_ENERGY_TYPE,
    CONF_MINIMUM_POWER,
    CONF_OBSERVATION_INTERVAL,
    CONF_OBSERVATION_WINDOW,
    CONF_POWER_ENTITY,
    CONF_RANKING_METHOD,
    CONF_SOURCE_ID,
    CONF_SOURCES,
    DEFAULT_CHALLENGE_CONFIRMATIONS,
    DEFAULT_CHALLENGE_THRESHOLD,
    DEFAULT_MINIMUM_POWER,
    DEFAULT_OBSERVATION_INTERVAL,
    DEFAULT_OBSERVATION_WINDOW,
    DEFAULT_RANKING_METHOD,
    DOMAIN,
    ENERGY_TYPE_CUMULATIVE,
    ENERGY_TYPE_MONTHLY,
    RANKING_METHOD_AVERAGE,
    RANKING_METHOD_PEAK,
    RANKING_METHOD_RECENT_WEIGHTED,
)
from .storage import DynamicEnergyStorage

_LOGGER = logging.getLogger(__name__)

_TOP_RANKING_LIMIT = 4


class DynamicEnergyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        storage: DynamicEnergyStorage,
    ) -> None:
        self.config_entry = config_entry
        self.storage = storage

        self._power_history: dict[str, deque[tuple[datetime, float]]] = defaultdict(
            deque
        )
        self._displayed_ranking: list[str] = []
        self._challenge_counts: dict[str, int] = defaultdict(int)
        self._challenge_target: str | None = None

        observation_interval = self._get_int_option(
            CONF_OBSERVATION_INTERVAL,
            DEFAULT_OBSERVATION_INTERVAL,
        )

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=observation_interval,
            ),
            config_entry=config_entry,
        )

    async def async_initialize(self) -> None:
        await self.storage.async_load()
        await self.async_config_entry_first_refresh()

    def _get_sources(
        self,
    ) -> list[dict[str, Any]]:
        sources = self.config_entry.options.get(
            CONF_SOURCES,
        )

        if sources is None:
            sources = self.config_entry.data.get(
                CONF_SOURCES,
                [],
            )

        return list(sources)

    def _get_int_option(
        self,
        key: str,
        default: int,
    ) -> int:
        try:
            value = int(
                self.config_entry.options.get(
                    key,
                    default,
                )
            )
        except TypeError, ValueError:
            return default

        return value

    def _get_float_option(
        self,
        key: str,
        default: float,
    ) -> float:
        try:
            value = float(
                self.config_entry.options.get(
                    key,
                    default,
                )
            )
        except TypeError, ValueError:
            return default

        return value

    def _get_ranking_method(self) -> str:
        method = self.config_entry.options.get(
            CONF_RANKING_METHOD,
            DEFAULT_RANKING_METHOD,
        )

        if method not in (
            RANKING_METHOD_AVERAGE,
            RANKING_METHOD_RECENT_WEIGHTED,
            RANKING_METHOD_PEAK,
        ):
            return DEFAULT_RANKING_METHOD

        return method

    async def _async_update_data(
        self,
    ) -> dict[str, Any]:
        sources = self._get_sources()

        current_power = self._calculate_current_power(
            sources,
        )

        monthly_energy = await self._async_update_energy(
            sources,
        )

        top_sources = self._update_ranking(
            sources,
        )

        return {
            "current_power": current_power,
            "monthly_energy": monthly_energy,
            "top_sources": top_sources,
        }

    def _calculate_current_power(
        self,
        sources: list[dict[str, Any]],
    ) -> float:
        total = 0.0

        for source in sources:
            power_entity = source.get(
                CONF_POWER_ENTITY,
            )

            if not power_entity:
                continue

            state = self.hass.states.get(
                power_entity,
            )

            if state is None:
                continue

            if state.state in (
                "unknown",
                "unavailable",
            ):
                continue

            try:
                power = float(state.state)
            except TypeError, ValueError:
                continue

            if power < 0:
                continue

            unit = str(
                state.attributes.get(
                    "unit_of_measurement",
                    "W",
                )
            ).lower()

            if unit == "kw":
                power *= 1000

            total += power

        return total

    async def _async_update_energy(
        self,
        sources: list[dict[str, Any]],
    ) -> float:
        month = dt_util.now().strftime("%Y-%m")

        for source in sources:
            source_id = source.get(
                CONF_SOURCE_ID,
            )

            fingerprint = source.get(
                "fingerprint",
            )

            energy_entity = source.get(
                CONF_ENERGY_ENTITY,
            )

            energy_type = source.get(
                CONF_ENERGY_TYPE,
            )

            if not source_id:
                continue

            if not fingerprint:
                continue

            if not energy_entity:
                continue

            if energy_type not in (
                ENERGY_TYPE_CUMULATIVE,
                ENERGY_TYPE_MONTHLY,
            ):
                continue

            state = self.hass.states.get(
                energy_entity,
            )

            if state is None:
                continue

            if state.state in (
                "unknown",
                "unavailable",
            ):
                continue

            try:
                raw_value = float(state.state)
            except TypeError, ValueError:
                continue

            if raw_value < 0:
                continue

            self.storage.ensure_source(
                fingerprint=fingerprint,
                source_id=source_id,
                energy_type=energy_type,
                baseline=(raw_value if energy_type == ENERGY_TYPE_CUMULATIVE else None),
                month=month,
            )

            if energy_type == ENERGY_TYPE_CUMULATIVE:
                monthly_value = self._process_cumulative(
                    fingerprint,
                    source_id,
                    month,
                    raw_value,
                )
            else:
                monthly_value = self._process_monthly(
                    fingerprint,
                    source_id,
                    month,
                    raw_value,
                )

            self.storage.set_monthly_value(
                fingerprint,
                source_id,
                month,
                monthly_value,
            )

        await self.storage.async_save()

        return self.storage.get_month_total(
            month,
        )

    def _process_cumulative(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
        raw_value: float,
    ) -> float:
        month_state = self.storage.get_month_state(
            fingerprint,
            source_id,
            month,
        )

        if month_state is None:
            return 0.0

        baseline = month_state.get(
            "baseline",
        )

        carry = float(
            month_state.get(
                "carry",
                0.0,
            )
        )

        last_raw = month_state.get(
            "last_raw",
        )

        if baseline is None:
            baseline = raw_value
            carry = 0.0

        if last_raw is not None:
            last_raw = float(last_raw)

            if raw_value < last_raw:
                previous_consumption = max(
                    0.0,
                    last_raw - float(baseline),
                )

                carry += previous_consumption
                baseline = raw_value

        current_segment = max(
            0.0,
            raw_value - float(baseline),
        )

        value = carry + current_segment

        self.storage.set_month_state(
            fingerprint,
            source_id,
            month,
            baseline=float(baseline),
            carry=carry,
            last_raw=raw_value,
            value=value,
        )

        return value

    def _process_monthly(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
        raw_value: float,
    ) -> float:
        month_state = self.storage.get_month_state(
            fingerprint,
            source_id,
            month,
        )

        if month_state is None:
            return raw_value

        carry = float(
            month_state.get(
                "carry",
                0.0,
            )
        )

        last_raw = month_state.get(
            "last_raw",
        )

        if last_raw is not None:
            last_raw = float(last_raw)

            if raw_value < last_raw:
                carry += max(
                    0.0,
                    last_raw,
                )

        value = carry + raw_value

        self.storage.set_month_state(
            fingerprint,
            source_id,
            month,
            carry=carry,
            last_raw=raw_value,
            value=value,
        )

        return value

    def _read_power(
        self,
        source: dict[str, Any],
    ) -> float | None:
        power_entity = source.get(
            CONF_POWER_ENTITY,
        )

        if not power_entity:
            return None

        state = self.hass.states.get(
            power_entity,
        )

        if state is None:
            return None

        if state.state in (
            "unknown",
            "unavailable",
        ):
            return None

        try:
            power = float(state.state)
        except TypeError, ValueError:
            return None

        if power < 0:
            return None

        unit = str(
            state.attributes.get(
                "unit_of_measurement",
                "W",
            )
        ).lower()

        if unit == "kw":
            power *= 1000

        return power

    def _update_ranking(
        self,
        sources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        now = dt_util.now()

        observation_window = max(
            1,
            self._get_int_option(
                CONF_OBSERVATION_WINDOW,
                DEFAULT_OBSERVATION_WINDOW,
            ),
        )

        minimum_power = max(
            0.0,
            self._get_float_option(
                CONF_MINIMUM_POWER,
                DEFAULT_MINIMUM_POWER,
            ),
        )

        active_ids: set[str] = set()
        current_values: dict[str, float] = {}

        for source in sources:
            source_id = source.get(
                CONF_SOURCE_ID,
            )

            if not source_id:
                continue

            active_ids.add(source_id)

            power = self._read_power(
                source,
            )

            history = self._power_history[source_id]

            if power is not None:
                history.append(
                    (
                        now,
                        power,
                    )
                )

            cutoff = now - timedelta(
                seconds=observation_window,
            )

            while history and history[0][0] < cutoff:
                history.popleft()

            if power is not None:
                current_values[source_id] = power

        for source_id in list(self._power_history):
            if source_id not in active_ids:
                del self._power_history[source_id]

        available = [
            source
            for source in sources
            if source.get(CONF_SOURCE_ID) in current_values
            and current_values[source[CONF_SOURCE_ID]] >= minimum_power
        ]

        scores = {
            source[CONF_SOURCE_ID]: self._calculate_ranking_score(
                source[CONF_SOURCE_ID],
            )
            for source in available
        }

        ordered = sorted(
            available,
            key=lambda source: (
                scores.get(
                    source[CONF_SOURCE_ID],
                    0.0,
                ),
                current_values.get(
                    source[CONF_SOURCE_ID],
                    0.0,
                ),
            ),
            reverse=True,
        )

        ordered_ids = [source[CONF_SOURCE_ID] for source in ordered]

        self._update_displayed_ranking(
            ordered_ids,
            scores,
            current_values,
        )

        source_by_id = {
            source[CONF_SOURCE_ID]: source
            for source in sources
            if source.get(CONF_SOURCE_ID)
        }

        month = dt_util.now().strftime(
            "%Y-%m",
        )

        result: list[dict[str, Any]] = []

        for source_id in self._displayed_ranking:
            source = source_by_id.get(
                source_id,
            )

            if source is None:
                continue

            fingerprint = source.get(
                "fingerprint",
            )

            monthly_energy = 0.0

            if fingerprint:
                monthly_energy = self.storage.get_monthly_value(
                    fingerprint,
                    source_id,
                    month,
                )

            result.append(
                {
                    "source_id": source_id,
                    "name": source.get(
                        "name",
                        source_id,
                    ),
                    "icon": source.get(
                        "icon",
                        "mdi:flash",
                    ),
                    "power": current_values.get(
                        source_id,
                        0.0,
                    ),
                    "ranking_score": scores.get(
                        source_id,
                        0.0,
                    ),
                    "monthly_energy": monthly_energy,
                }
            )

        return result

    def _calculate_ranking_score(
        self,
        source_id: str,
    ) -> float:
        history = self._power_history.get(
            source_id,
        )

        if not history:
            return 0.0

        values = [value for _, value in history]

        method = self._get_ranking_method()

        if method == RANKING_METHOD_PEAK:
            return max(values)

        if method == RANKING_METHOD_RECENT_WEIGHTED:
            weights = range(
                1,
                len(values) + 1,
            )

            return sum(
                value * weight
                for value, weight in zip(
                    values,
                    weights,
                )
            ) / sum(weights)

        return sum(values) / len(values)

    def _update_displayed_ranking(
        self,
        ordered_ids: list[str],
        scores: dict[str, float],
        current_values: dict[str, float],
    ) -> None:
        available_ids = set(
            ordered_ids,
        )

        current = [
            source_id
            for source_id in self._displayed_ranking
            if source_id in available_ids
        ]

        for source_id in self._displayed_ranking:
            if source_id not in available_ids:
                self._challenge_counts.pop(
                    source_id,
                    None,
                )

        if len(current) < _TOP_RANKING_LIMIT:
            current = [source_id for source_id in ordered_ids[:_TOP_RANKING_LIMIT]]

            self._challenge_target = None
            self._challenge_counts.clear()

            if current != self._displayed_ranking:
                self._displayed_ranking = current

            return

        displayed_scores = {
            source_id: scores.get(
                source_id,
                0.0,
            )
            for source_id in current
        }

        current_fourth = current[_TOP_RANKING_LIMIT - 1]

        current_fourth_score = displayed_scores.get(
            current_fourth,
            0.0,
        )

        challenger = next(
            (source_id for source_id in ordered_ids if source_id not in current),
            None,
        )

        if challenger is None:
            self._challenge_target = None
            self._challenge_counts.clear()

            return

        threshold = max(
            0.0,
            self._get_float_option(
                CONF_CHALLENGE_THRESHOLD,
                DEFAULT_CHALLENGE_THRESHOLD,
            ),
        )

        required_score = current_fourth_score * (1.0 + threshold / 100.0)

        challenger_score = scores.get(
            challenger,
            0.0,
        )

        if challenger_score <= required_score:
            self._challenge_target = None
            self._challenge_counts.clear()

            return

        if self._challenge_target != challenger:
            self._challenge_target = challenger
            self._challenge_counts.clear()

        self._challenge_counts[challenger] += 1

        confirmations = max(
            1,
            self._get_int_option(
                CONF_CHALLENGE_CONFIRMATIONS,
                DEFAULT_CHALLENGE_CONFIRMATIONS,
            ),
        )

        if self._challenge_counts[challenger] < confirmations:
            return

        replacement = challenger

        self._displayed_ranking = [
            source_id for source_id in current if source_id != current_fourth
        ]

        self._displayed_ranking.append(
            replacement,
        )

        self._displayed_ranking = [
            source_id
            for source_id in ordered_ids
            if source_id in self._displayed_ranking
        ][:_TOP_RANKING_LIMIT]

        self._challenge_target = None
        self._challenge_counts.clear()
