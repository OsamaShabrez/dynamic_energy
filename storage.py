from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


class DynamicEnergyStorage:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
        )

        self._data: dict[str, Any] = {
            "sources": {},
        }

    async def async_load(self) -> None:
        stored = await self._store.async_load()

        if stored:
            self._data = stored

        self._data.setdefault("sources", {})

        for source in self._data["sources"].values():
            source.setdefault("epochs", {})
            source.setdefault("history", {})

            for epoch in source["epochs"].values():
                epoch.setdefault("created_at", datetime.now().isoformat())
                epoch.setdefault("energy_type", "cumulative")
                epoch.setdefault("months", {})
                epoch.setdefault("baselines", {})

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    def get_source(
        self,
        fingerprint: str,
    ) -> dict[str, Any] | None:
        return self._data["sources"].get(fingerprint)

    def ensure_source(
        self,
        fingerprint: str,
        source_id: str,
        energy_type: str,
        baseline: float | None,
        month: str,
    ) -> dict[str, Any]:
        source = self._data["sources"].get(fingerprint)

        if source is None:
            source = {
                "fingerprint": fingerprint,
                "created_at": datetime.now().isoformat(),
                "epochs": {},
                "history": {},
            }

            self._data["sources"][fingerprint] = source

        source.setdefault("epochs", {})
        source.setdefault("history", {})

        if source_id not in source["epochs"]:
            source["epochs"][source_id] = {
                "created_at": datetime.now().isoformat(),
                "energy_type": energy_type,
                "baselines": {},
                "months": {},
            }

        epoch = source["epochs"][source_id]

        epoch.setdefault(
            "energy_type",
            energy_type,
        )

        epoch.setdefault(
            "baselines",
            {},
        )

        epoch.setdefault(
            "months",
            {},
        )

        if (
            energy_type == "cumulative"
            and month not in epoch["baselines"]
            and baseline is not None
        ):
            epoch["baselines"][month] = baseline

        self.ensure_month(
            fingerprint,
            source_id,
            month,
        )

        return source

    def ensure_month(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
    ) -> dict[str, Any] | None:
        epoch = self.get_epoch(
            fingerprint,
            source_id,
        )

        if epoch is None:
            return None

        months = epoch.setdefault(
            "months",
            {},
        )

        if month not in months:
            months[month] = {
                "baseline": None,
                "carry": 0.0,
                "last_raw": None,
                "value": 0.0,
            }

        return months[month]

    def get_epoch(
        self,
        fingerprint: str,
        source_id: str,
    ) -> dict[str, Any] | None:
        source = self._data["sources"].get(fingerprint)

        if source is None:
            return None

        return source.get("epochs", {}).get(source_id)

    def get_month_state(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
    ) -> dict[str, Any] | None:
        return self.ensure_month(
            fingerprint,
            source_id,
            month,
        )

    def set_month_state(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
        *,
        baseline: float | None = None,
        carry: float | None = None,
        last_raw: float | None = None,
        value: float | None = None,
    ) -> None:
        month_state = self.ensure_month(
            fingerprint,
            source_id,
            month,
        )

        if month_state is None:
            return

        if baseline is not None:
            month_state["baseline"] = baseline

        if carry is not None:
            month_state["carry"] = carry

        if last_raw is not None:
            month_state["last_raw"] = last_raw

        if value is not None:
            month_state["value"] = value

    def get_baseline(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
    ) -> float | None:
        month_state = self.get_month_state(
            fingerprint,
            source_id,
            month,
        )

        if month_state is None:
            return None

        baseline = month_state.get("baseline")

        if baseline is None:
            return None

        return float(baseline)

    def set_baseline(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
        value: float,
    ) -> None:
        self.set_month_state(
            fingerprint,
            source_id,
            month,
            baseline=value,
        )

    def get_monthly_value(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
    ) -> float:
        month_state = self.get_month_state(
            fingerprint,
            source_id,
            month,
        )

        if month_state is None:
            return 0.0

        return float(
            month_state.get(
                "value",
                0.0,
            )
        )

    def set_monthly_value(
        self,
        fingerprint: str,
        source_id: str,
        month: str,
        value: float,
    ) -> None:
        month_state = self.get_month_state(
            fingerprint,
            source_id,
            month,
        )

        if month_state is None:
            return

        month_state["value"] = max(
            0.0,
            float(value),
        )

        source = self._data["sources"].get(fingerprint)

        if source is None:
            return

        history = source.setdefault(
            "history",
            {},
        )

        month_history = history.setdefault(
            month,
            {},
        )

        month_history[source_id] = max(
            0.0,
            float(value),
        )

    def get_source_history(
        self,
        fingerprint: str,
    ) -> dict[str, Any]:
        source = self._data["sources"].get(fingerprint)

        if source is None:
            return {}

        return source

    def get_month_total(
        self,
        month: str,
    ) -> float:
        total = 0.0

        for source in self._data["sources"].values():
            history = source.get(
                "history",
                {},
            )

            month_history = history.get(
                month,
                {},
            )

            total += sum(float(value) for value in month_history.values())

        return total
