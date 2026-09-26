from __future__ import annotations

import asyncio

from homeassistant.core import HomeAssistant

from custom_components.dynamic_energy.storage import (
    DynamicEnergyStorage,
)


def create_hass(storage_path):
    return HomeAssistant(str(storage_path))


def run(coro):
    return asyncio.run(coro)


def test_monthly_accounting_survives_restart(tmp_path):
    async def scenario():
        hass = create_hass(tmp_path)

        try:
            storage = DynamicEnergyStorage(hass)

            fingerprint = "plug|energy|monthly"
            source_id = "plug"
            month = "2026-09"

            storage.ensure_source(
                fingerprint=fingerprint,
                source_id=source_id,
                energy_type="monthly",
                baseline=None,
                month=month,
            )

            storage.set_month_state(
                fingerprint,
                source_id,
                month,
                carry=12.5,
                last_raw=4.5,
                value=17.0,
            )

            storage.set_monthly_value(
                fingerprint,
                source_id,
                month,
                17.0,
            )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            month_state = restarted_storage.get_month_state(
                fingerprint,
                source_id,
                month,
            )

            assert month_state is not None
            assert month_state["carry"] == 12.5
            assert month_state["last_raw"] == 4.5
            assert month_state["value"] == 17.0

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    source_id,
                    month,
                )
                == 17.0
            )

            assert restarted_storage.get_month_total(month) == 17.0
        finally:
            await restarted_hass.async_stop()

    run(scenario())


def test_cumulative_accounting_survives_restart(tmp_path):
    async def scenario():
        hass = create_hass(tmp_path)

        try:
            storage = DynamicEnergyStorage(hass)

            fingerprint = "plug|energy|cumulative"
            source_id = "plug"
            month = "2026-09"

            storage.ensure_source(
                fingerprint=fingerprint,
                source_id=source_id,
                energy_type="cumulative",
                baseline=100.0,
                month=month,
            )

            storage.set_month_state(
                fingerprint,
                source_id,
                month,
                baseline=100.0,
                carry=25.0,
                last_raw=140.0,
                value=65.0,
            )

            storage.set_monthly_value(
                fingerprint,
                source_id,
                month,
                65.0,
            )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            month_state = restarted_storage.get_month_state(
                fingerprint,
                source_id,
                month,
            )

            assert month_state is not None
            assert month_state["baseline"] == 100.0
            assert month_state["carry"] == 25.0
            assert month_state["last_raw"] == 140.0
            assert month_state["value"] == 65.0

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    source_id,
                    month,
                )
                == 65.0
            )

            assert restarted_storage.get_month_total(month) == 65.0
        finally:
            await restarted_hass.async_stop()

    run(scenario())


def test_multiple_sources_survive_restart(tmp_path):
    async def scenario():
        hass = create_hass(tmp_path)

        try:
            storage = DynamicEnergyStorage(hass)

            month = "2026-09"

            sources = [
                (
                    "plug-a|energy|monthly",
                    "plug-a",
                    10.0,
                ),
                (
                    "plug-b|energy|monthly",
                    "plug-b",
                    25.0,
                ),
                (
                    "plug-c|energy|monthly",
                    "plug-c",
                    40.0,
                ),
            ]

            for fingerprint, source_id, value in sources:
                storage.ensure_source(
                    fingerprint=fingerprint,
                    source_id=source_id,
                    energy_type="monthly",
                    baseline=None,
                    month=month,
                )

                storage.set_month_state(
                    fingerprint,
                    source_id,
                    month,
                    last_raw=value,
                    value=value,
                )

                storage.set_monthly_value(
                    fingerprint,
                    source_id,
                    month,
                    value,
                )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            for fingerprint, source_id, value in sources:
                assert (
                    restarted_storage.get_monthly_value(
                        fingerprint,
                        source_id,
                        month,
                    )
                    == value
                )

            assert restarted_storage.get_month_total(month) == 75.0
        finally:
            await restarted_hass.async_stop()

    run(scenario())


def test_historical_months_survive_restart(tmp_path):
    async def scenario():
        hass = create_hass(tmp_path)

        try:
            storage = DynamicEnergyStorage(hass)

            fingerprint = "plug|energy|monthly"
            source_id = "plug"

            history = {
                "2026-07": 30.0,
                "2026-08": 45.0,
                "2026-09": 60.0,
            }

            for month, value in history.items():
                storage.ensure_source(
                    fingerprint=fingerprint,
                    source_id=source_id,
                    energy_type="monthly",
                    baseline=None,
                    month=month,
                )

                storage.set_monthly_value(
                    fingerprint,
                    source_id,
                    month,
                    value,
                )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            for month, value in history.items():
                assert (
                    restarted_storage.get_monthly_value(
                        fingerprint,
                        source_id,
                        month,
                    )
                    == value
                )

                assert restarted_storage.get_month_total(month) == value

            assert restarted_storage.get_month_total("2026-07") == 30.0

            assert restarted_storage.get_month_total("2026-08") == 45.0

            assert restarted_storage.get_month_total("2026-09") == 60.0
        finally:
            await restarted_hass.async_stop()

    run(scenario())


def test_removed_source_history_survives_restart(tmp_path):
    async def scenario():
        hass = create_hass(tmp_path)

        try:
            storage = DynamicEnergyStorage(hass)

            month = "2026-09"

            fingerprint = "removed-plug|energy|monthly"
            source_id = "removed-plug"

            storage.ensure_source(
                fingerprint=fingerprint,
                source_id=source_id,
                energy_type="monthly",
                baseline=None,
                month=month,
            )

            storage.set_monthly_value(
                fingerprint,
                source_id,
                month,
                55.0,
            )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    source_id,
                    month,
                )
                == 55.0
            )

            assert restarted_storage.get_month_total(month) == 55.0

            source = restarted_storage.get_source_history(
                fingerprint,
            )

            assert source
            assert source["history"][month][source_id] == 55.0
        finally:
            await restarted_hass.async_stop()

    run(scenario())


def test_readded_source_does_not_lose_historical_data_after_restart(
    tmp_path,
):
    async def scenario():
        hass = create_hass(tmp_path)

        try:
            storage = DynamicEnergyStorage(hass)

            month = "2026-09"

            fingerprint = "plug|energy|monthly"
            source_id = "plug"

            storage.ensure_source(
                fingerprint=fingerprint,
                source_id=source_id,
                energy_type="monthly",
                baseline=None,
                month=month,
            )

            storage.set_monthly_value(
                fingerprint,
                source_id,
                month,
                100.0,
            )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    source_id,
                    month,
                )
                == 100.0
            )

            assert restarted_storage.get_month_total(month) == 100.0

            new_month = "2026-10"

            restarted_storage.ensure_source(
                fingerprint=fingerprint,
                source_id=source_id,
                energy_type="monthly",
                baseline=None,
                month=new_month,
            )

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    source_id,
                    new_month,
                )
                == 0.0
            )

            assert (
                restarted_storage.get_month_total(
                    new_month,
                )
                == 0.0
            )

            assert restarted_storage.get_month_total(month) == 100.0
        finally:
            await restarted_hass.async_stop()

    run(scenario())


def test_storage_metadata_survives_restart(tmp_path):
    async def scenario():
        hass = create_hass(tmp_path)

        try:
            storage = DynamicEnergyStorage(hass)

            fingerprint = "plug|energy|cumulative"
            source_id = "plug"
            month = "2026-09"

            storage.ensure_source(
                fingerprint=fingerprint,
                source_id=source_id,
                energy_type="cumulative",
                baseline=500.0,
                month=month,
            )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            source = restarted_storage.get_source_history(
                fingerprint,
            )

            assert source
            assert source["fingerprint"] == fingerprint
            assert "created_at" in source
            assert "epochs" in source
            assert "history" in source

            epoch = source["epochs"][source_id]

            assert "created_at" in epoch
            assert epoch["energy_type"] == "cumulative"
            assert "baselines" in epoch
            assert "months" in epoch

            assert epoch["baselines"][month] == 500.0
        finally:
            await restarted_hass.async_stop()

    run(scenario())


def test_ranking_state_is_not_persisted(tmp_path):
    async def scenario():
        hass = create_hass(tmp_path)

        try:
            storage = DynamicEnergyStorage(hass)

            fingerprint = "plug|energy|monthly"
            source_id = "plug"
            month = "2026-09"

            storage.ensure_source(
                fingerprint=fingerprint,
                source_id=source_id,
                energy_type="monthly",
                baseline=None,
                month=month,
            )

            storage.set_monthly_value(
                fingerprint,
                source_id,
                month,
                20.0,
            )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            source = restarted_storage.get_source_history(
                fingerprint,
            )

            assert source

            assert "ranking" not in source
            assert "ranking_history" not in source
            assert "displayed_ranking" not in source
            assert "challenge_counts" not in source
            assert "power_history" not in source

            epoch = source["epochs"][source_id]

            assert "ranking" not in epoch
            assert "ranking_history" not in epoch
            assert "power_history" not in epoch
        finally:
            await restarted_hass.async_stop()

    run(scenario())


def test_readded_source_starts_fresh_epoch_and_keeps_history(
    tmp_path,
):
    async def scenario():
        hass = create_hass(tmp_path)

        fingerprint = "plug|energy|monthly"
        old_source_id = "old-plug-id"
        new_source_id = "new-plug-id"
        month = "2026-09"

        try:
            storage = DynamicEnergyStorage(hass)

            storage.ensure_source(
                fingerprint=fingerprint,
                source_id=old_source_id,
                energy_type="monthly",
                baseline=None,
                month=month,
            )

            storage.set_monthly_value(
                fingerprint,
                old_source_id,
                month,
                100.0,
            )

            await storage.async_save()
        finally:
            await hass.async_stop()

        restarted_hass = create_hass(tmp_path)

        try:
            restarted_storage = DynamicEnergyStorage(
                restarted_hass,
            )

            await restarted_storage.async_load()

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    old_source_id,
                    month,
                )
                == 100.0
            )

            assert restarted_storage.get_month_total(month) == 100.0

            restarted_storage.ensure_source(
                fingerprint=fingerprint,
                source_id=new_source_id,
                energy_type="monthly",
                baseline=None,
                month=month,
            )

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    new_source_id,
                    month,
                )
                == 0.0
            )

            assert restarted_storage.get_month_total(month) == 100.0

            restarted_storage.set_monthly_value(
                fingerprint,
                new_source_id,
                month,
                15.0,
            )

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    old_source_id,
                    month,
                )
                == 100.0
            )

            assert (
                restarted_storage.get_monthly_value(
                    fingerprint,
                    new_source_id,
                    month,
                )
                == 15.0
            )

            assert restarted_storage.get_month_total(month) == 115.0

            source = restarted_storage.get_source_history(
                fingerprint,
            )

            assert source is not None

            epochs = source["epochs"]

            assert old_source_id in epochs
            assert new_source_id in epochs

            assert epochs[old_source_id]["months"][month]["value"] == 100.0

            assert epochs[new_source_id]["months"][month]["value"] == 15.0

            await restarted_storage.async_save()
        finally:
            await restarted_hass.async_stop()

        final_hass = create_hass(tmp_path)

        try:
            final_storage = DynamicEnergyStorage(
                final_hass,
            )

            await final_storage.async_load()

            assert (
                final_storage.get_monthly_value(
                    fingerprint,
                    old_source_id,
                    month,
                )
                == 100.0
            )

            assert (
                final_storage.get_monthly_value(
                    fingerprint,
                    new_source_id,
                    month,
                )
                == 15.0
            )

            assert final_storage.get_month_total(month) == 115.0
        finally:
            await final_hass.async_stop()

    run(scenario())
