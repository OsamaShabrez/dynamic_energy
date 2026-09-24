from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_ENERGY_ENTITY,
    CONF_ENERGY_TYPE,
    CONF_ICON,
    CONF_NAME,
    CONF_OBSERVATION_INTERVAL,
    CONF_POWER_ENTITY,
    CONF_SOURCE_ID,
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
    entry_id: str | None = None,
) -> ConfigEntry | None:
    """Return the Dynamic Energy config entry."""
    if entry_id:
        return hass.config_entries.async_get_entry(entry_id)

    entries = hass.config_entries.async_entries(DOMAIN)

    if not entries:
        return None

    return entries[0]


def _fingerprint(source: dict[str, Any]) -> str:
    """Create a stable fingerprint for a source."""
    return SOURCE_FINGERPRINT_SEPARATOR.join(
        [
            source[CONF_POWER_ENTITY],
            source[CONF_ENERGY_ENTITY],
            source[CONF_ENERGY_TYPE],
        ]
    )


def _normalise_source(source: dict[str, Any]) -> dict[str, Any]:
    """Normalize a source received from the frontend."""
    import uuid

    source_id = source.get(CONF_SOURCE_ID)

    if not source_id:
        source_id = str(uuid.uuid4())

    normalized = {
        CONF_SOURCE_ID: str(source_id),
        CONF_NAME: str(source.get(CONF_NAME, "")).strip(),
        CONF_POWER_ENTITY: str(source.get(CONF_POWER_ENTITY, "")).strip(),
        CONF_ENERGY_ENTITY: str(source.get(CONF_ENERGY_ENTITY, "")).strip(),
        CONF_ENERGY_TYPE: str(
            source.get(CONF_ENERGY_TYPE, ENERGY_TYPE_MONTHLY)
        ).strip(),
        CONF_ICON: str(source.get(CONF_ICON, "mdi:flash")).strip() or "mdi:flash",
    }

    normalized["fingerprint"] = _fingerprint(normalized)

    return normalized


def _validate_sources(
    sources: list[dict[str, Any]],
) -> None:
    """Validate configured energy sources."""
    names: set[str] = set()
    fingerprints: set[str] = set()

    for source in sources:
        name = source[CONF_NAME]

        if not name:
            raise vol.Invalid("Every smart plug must have a name.")

        if not source[CONF_POWER_ENTITY]:
            raise vol.Invalid(f"Smart plug '{name}' is missing a power sensor.")

        if not source[CONF_ENERGY_ENTITY]:
            raise vol.Invalid(f"Smart plug '{name}' is missing an energy sensor.")

        if source[CONF_ENERGY_TYPE] not in {
            ENERGY_TYPE_MONTHLY,
            ENERGY_TYPE_CUMULATIVE,
        }:
            raise vol.Invalid(f"Smart plug '{name}' has an invalid energy type.")

        name_key = name.casefold()

        if name_key in names:
            raise vol.Invalid(f"Duplicate smart plug name: {name}")

        names.add(name_key)

        fingerprint = source["fingerprint"]

        if fingerprint in fingerprints:
            raise vol.Invalid(f"Duplicate sensor configuration for smart plug: {name}")

        fingerprints.add(fingerprint)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_GET_CONFIG,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return Dynamic Energy configuration."""
    entry = _get_entry(hass)

    if entry is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Dynamic Energy config entry not found",
        )
        return

    sources = []

    for source in entry.options.get(CONF_SOURCES, []):
        normalized = _normalise_source(source)

        sources.append(
            {
                CONF_SOURCE_ID: normalized[CONF_SOURCE_ID],
                CONF_NAME: normalized[CONF_NAME],
                CONF_POWER_ENTITY: normalized[CONF_POWER_ENTITY],
                CONF_ENERGY_ENTITY: normalized[CONF_ENERGY_ENTITY],
                CONF_ENERGY_TYPE: normalized[CONF_ENERGY_TYPE],
                CONF_ICON: normalized[CONF_ICON],
            }
        )

    connection.send_result(
        msg["id"],
        {
            "entry_id": entry.entry_id,
            "observation_interval": entry.options.get(
                CONF_OBSERVATION_INTERVAL,
                10,
            ),
            "sources": sources,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_SAVE_CONFIG,
        vol.Required("entry_id"): str,
        vol.Required("sources"): list,
        vol.Required("observation_interval"): vol.All(
            vol.Coerce(int),
            vol.Range(
                min=MIN_OBSERVATION_INTERVAL,
                max=MAX_OBSERVATION_INTERVAL,
            ),
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
    """Save Dynamic Energy configuration."""
    entry = _get_entry(
        hass,
        msg["entry_id"],
    )

    if entry is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Dynamic Energy config entry not found",
        )
        return

    try:
        sources = [_normalise_source(source) for source in msg["sources"]]

        _validate_sources(sources)

    except vol.Invalid as err:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            str(err),
        )
        return

    options = dict(entry.options)

    options[CONF_SOURCES] = sources
    options[CONF_OBSERVATION_INTERVAL] = int(msg["observation_interval"])

    hass.config_entries.async_update_entry(
        entry,
        options=options,
    )

    if entry.state.name == "LOADED":
        await hass.config_entries.async_reload(entry.entry_id)

    connection.send_result(
        msg["id"],
        {
            "success": True,
            "entry_id": entry.entry_id,
        },
    )


@callback
def async_register_websocket_commands(
    hass: HomeAssistant,
) -> None:
    """Register Dynamic Energy WebSocket commands."""
    websocket_api.async_register_command(
        hass,
        websocket_get_config,
    )

    websocket_api.async_register_command(
        hass,
        websocket_save_config,
    )
