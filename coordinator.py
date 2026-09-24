from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENERGY_ENTITY,
    CONF_ENERGY_TYPE,
    CONF_OBSERVATION_INTERVAL,
    CONF_POWER_ENTITY,
    CONF_SOURCE_ID,
    CONF_SOURCES,
    DEFAULT_OBSERVATION_INTERVAL,
    DOMAIN,
    ENERGY_TYPE_CUMULATIVE,
    ENERGY_TYPE_MONTHLY,
)
from .storage import DynamicEnergyStorage

_LOGGER = logging.getLogger(__name__)


class DynamicEnergyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        storage: DynamicEnergyStorage,
    ) -> None:
        observation_interval = int(
            config_entry.options.get(
                CONF_OBSERVATION_INTERVAL,
                DEFAULT_OBSERVATION_INTERVAL,
            )
        )

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=observation_interval),
            config_entry=config_entry,
        )

        self.config_entry = config_entry
        self.storage = storage

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

    async def _async_update_data(
        self,
    ) -> dict[str, Any]:
        sources = self._get_sources()

        current_power = self._calculate_current_power(sources)

        monthly_energy = await self._async_update_energy(sources)

        return {
            "current_power": current_power,
            "monthly_energy": monthly_energy,
        }

    def _calculate_current_power(
        self,
        sources: list[dict[str, Any]],
    ) -> float:
        total = 0.0

        for source in sources:
            power_entity = source.get(CONF_POWER_ENTITY)

            if not power_entity:
                continue

            state = self.hass.states.get(power_entity)

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

            total += power

        return total

    async def _async_update_energy(
        self,
        sources: list[dict[str, Any]],
    ) -> float:
        month = dt_util.now().strftime("%Y-%m")

        for source in sources:
            source_id = source.get(CONF_SOURCE_ID)

            fingerprint = source.get("fingerprint")

            energy_entity = source.get(CONF_ENERGY_ENTITY)

            energy_type = source.get(CONF_ENERGY_TYPE)

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

            state = self.hass.states.get(energy_entity)

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

        return self.storage.get_month_total(month)

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

        baseline = month_state.get("baseline")

        carry = float(
            month_state.get(
                "carry",
                0.0,
            )
        )

        last_raw = month_state.get("last_raw")

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

        last_raw = month_state.get("last_raw")

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
