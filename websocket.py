from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_ENERGY_ENTITY,
    CONF_ENERGY_TYPE,
    CONF_ICON,
    CONF_OBSERVATION_INTERVAL,
    CONF_POWER_ENTITY,
    CONF_SOURCE_ID,
    CONF_SOURCE_NAME,
    CONF_SOURCES,
    DOMAIN,
    ENERGY_TYPE_CUMULATIVE,
    ENERGY_TYPE_MONTHLY,
    MAX_OBSERVATION_INTERVAL,
    MIN_OBSERVATION_INTERVAL,
    SOURCE_FINGERPRINT_SEPARATOR,
    WS_TYPE_GET_CONFIG,
    WS_TYPE_SAVE_CONFIG,
)


def _get_entry(
    hass: HomeAssistant,
) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)

    if not entries:
        return None

    return entries[0]


def _fingerprint(
    source: dict[str, Any],
) -> str:
    return SOURCE_FINGERPRINT_SEPARATOR.join(
        [
            str(
                source.get(
                    CONF_POWER_ENTITY,
                    "",
                )
            ),
            str(
                source.get(
                    CONF_ENERGY_ENTITY,
                    "",
                )
            ),
            str(
                source.get(
                    CONF_ENERGY_TYPE,
                    "",
                )
            ),
        ]
    )


def _normalise_source(
    source: dict[str, Any],
    *,
    source_id: str | None = None,
) -> dict[str, Any]:
    result = {
        CONF_SOURCE_ID: source_id or str(uuid4()),
        CONF_SOURCE_NAME: str(
            source.get(
                CONF_SOURCE_NAME,
                "",
            )
        ).strip(),
        CONF_POWER_ENTITY: str(
            source.get(
                CONF_POWER_ENTITY,
                "",
            )
        ),
        CONF_ENERGY_ENTITY: str(
            source.get(
                CONF_ENERGY_ENTITY,
                "",
            )
        ),
        CONF_ENERGY_TYPE: source.get(
            CONF_ENERGY_TYPE,
            ENERGY_TYPE_MONTHLY,
        ),
        CONF_ICON: str(
            source.get(
                CONF_ICON,
                "",
            )
        ).strip(),
    }

    result["fingerprint"] = _fingerprint(result)

    return result


def _validate_sources(
    sources: list[dict[str, Any]],
) -> str | None:
    names: set[str] = set()
    fingerprints: set[str] = set()

    for source in sources:
        name = str(
            source.get(
                CONF_SOURCE_NAME,
                "",
            )
        ).strip()

        power_entity = source.get(CONF_POWER_ENTITY)

        energy_entity = source.get(CONF_ENERGY_ENTITY)

        energy_type = source.get(CONF_ENERGY_TYPE)

        if not name:
            return "invalid_source"

        if not power_entity:
            return "invalid_source"

        if not energy_entity:
            return "invalid_source"

        if energy_type not in (
            ENERGY_TYPE_MONTHLY,
            ENERGY_TYPE_CUMULATIVE,
        ):
            return "invalid_source"

        normalized_name = name.casefold()

        if normalized_name in names:
            return "duplicate_source_name"

        names.add(normalized_name)

        fingerprint = _fingerprint(source)

        if fingerprint in fingerprints:
            return "duplicate_source"

        fingerprints.add(fingerprint)

    return None


@callback
def _find_source(
    sources: list[dict[str, Any]],
    source_id: str,
) -> dict[str, Any] | None:
    for source in sources:
        if source.get(CONF_SOURCE_ID) == source_id:
            return source

    return None


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_GET_CONFIG,
    }
)
@websocket_api.require_admin
@callback
def websocket_get_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    entry = _get_entry(hass)

    if entry is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Dynamic Energy is not configured",
        )
        return

    sources = list(
        entry.options.get(
            CONF_SOURCES,
            entry.data.get(
                CONF_SOURCES,
                [],
            ),
        )
    )

    observation_interval = int(
        entry.options.get(
            CONF_OBSERVATION_INTERVAL,
            10,
        )
    )

    connection.send_result(
        msg["id"],
        {
            "entry_id": entry.entry_id,
            "observation_interval": observation_interval,
            "sources": sources,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_SAVE_CONFIG,
        vol.Required("entry_id"): str,
        vol.Required(CONF_OBSERVATION_INTERVAL): vol.All(
            vol.Coerce(int),
            vol.Range(
                min=MIN_OBSERVATION_INTERVAL,
                max=MAX_OBSERVATION_INTERVAL,
            ),
        ),
        vol.Required(CONF_SOURCES): vol.All(
            list,
        ),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_save_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])

    if entry is None or entry.domain != DOMAIN:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Dynamic Energy config entry not found",
        )
        return

    submitted_sources = msg[CONF_SOURCES]

    current_sources = list(
        entry.options.get(
            CONF_SOURCES,
            entry.data.get(
                CONF_SOURCES,
                [],
            ),
        )
    )

    current_by_id = {
        source.get(CONF_SOURCE_ID): source
        for source in current_sources
        if source.get(CONF_SOURCE_ID)
    }

    normalized_sources: list[dict[str, Any]] = []

    for submitted_source in submitted_sources:
        if not isinstance(
            submitted_source,
            dict,
        ):
            connection.send_error(
                msg["id"],
                websocket_api.ERR_INVALID_FORMAT,
                "Invalid smart plug configuration",
            )
            return

        source_id = submitted_source.get(CONF_SOURCE_ID)

        if source_id and source_id in current_by_id:
            normalized = _normalise_source(
                submitted_source,
                source_id=source_id,
            )
        else:
            normalized = _normalise_source(submitted_source)

        normalized_sources.append(normalized)

    validation_error = _validate_sources(normalized_sources)

    if validation_error:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            validation_error,
        )
        return

    new_options = {
        CONF_SOURCES: normalized_sources,
        CONF_OBSERVATION_INTERVAL: int(msg[CONF_OBSERVATION_INTERVAL]),
    }

    hass.config_entries.async_update_entry(
        entry,
        options=new_options,
    )

    reloaded = await hass.config_entries.async_reload(entry.entry_id)

    if not reloaded:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_UNKNOWN_ERROR,
            "Dynamic Energy could not be reloaded",
        )
        return

    connection.send_result(
        msg["id"],
        {
            "success": True,
            "sources": normalized_sources,
            "observation_interval": int(msg[CONF_OBSERVATION_INTERVAL]),
        },
    )


def async_register_websocket_commands(
    hass: HomeAssistant,
) -> None:
    websocket_api.async_register_command(
        hass,
        websocket_get_config,
    )

    websocket_api.async_register_command(
        hass,
        websocket_save_config,
    )
