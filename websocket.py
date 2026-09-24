from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    CHALLENGE_CONFIRMATIONS_OPTIONS,
    CHALLENGE_THRESHOLD_OPTIONS,
    CONF_CHALLENGE_CONFIRMATIONS,
    CONF_CHALLENGE_THRESHOLD,
    CONF_ENERGY_ENTITY,
    CONF_ENERGY_TYPE,
    CONF_ICON,
    CONF_MINIMUM_POWER,
    CONF_OBSERVATION_INTERVAL,
    CONF_OBSERVATION_WINDOW,
    CONF_POWER_ENTITY,
    CONF_RANKING_METHOD,
    CONF_SOURCE_ID,
    CONF_SOURCE_NAME,
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
    MAX_CHALLENGE_CONFIRMATIONS,
    MAX_CHALLENGE_THRESHOLD,
    MAX_OBSERVATION_INTERVAL,
    MAX_OBSERVATION_WINDOW,
    MIN_CHALLENGE_CONFIRMATIONS,
    MIN_CHALLENGE_THRESHOLD,
    MIN_OBSERVATION_INTERVAL,
    MIN_OBSERVATION_WINDOW,
    MINIMUM_POWER_OPTIONS,
    OBSERVATION_INTERVAL_OPTIONS,
    OBSERVATION_WINDOW_OPTIONS,
    RANKING_METHOD_OPTIONS,
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
    source_id = source.get(CONF_SOURCE_ID)

    if not source_id:
        source_id = str(uuid4())

    normalized = {
        CONF_SOURCE_ID: str(source_id),
        CONF_SOURCE_NAME: str(source.get(CONF_SOURCE_NAME, "")).strip(),
        CONF_POWER_ENTITY: str(source.get(CONF_POWER_ENTITY, "")).strip(),
        CONF_ENERGY_ENTITY: str(source.get(CONF_ENERGY_ENTITY, "")).strip(),
        CONF_ENERGY_TYPE: str(
            source.get(
                CONF_ENERGY_TYPE,
                ENERGY_TYPE_MONTHLY,
            )
        ).strip(),
        CONF_ICON: str(
            source.get(
                CONF_ICON,
                "mdi:flash",
            )
        ).strip()
        or "mdi:flash",
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
        name = source[CONF_SOURCE_NAME]

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


def _get_int_option(
    options: dict[str, Any],
    key: str,
    default: int,
) -> int:
    """Return an integer option with a safe fallback."""
    try:
        return int(options.get(key, default))
    except TypeError, ValueError:
        return default


def _get_float_option(
    options: dict[str, Any],
    key: str,
    default: float,
) -> float:
    """Return a float option with a safe fallback."""
    try:
        return float(options.get(key, default))
    except TypeError, ValueError:
        return default


def _get_ranking_method(
    options: dict[str, Any],
) -> str:
    """Return a valid ranking method."""
    method = options.get(
        CONF_RANKING_METHOD,
        DEFAULT_RANKING_METHOD,
    )

    if method not in RANKING_METHOD_OPTIONS:
        return DEFAULT_RANKING_METHOD

    return str(method)


def _get_config_options(
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return normalized monitoring configuration."""
    options = entry.options

    return {
        CONF_OBSERVATION_INTERVAL: _get_int_option(
            options,
            CONF_OBSERVATION_INTERVAL,
            DEFAULT_OBSERVATION_INTERVAL,
        ),
        CONF_OBSERVATION_WINDOW: _get_int_option(
            options,
            CONF_OBSERVATION_WINDOW,
            DEFAULT_OBSERVATION_WINDOW,
        ),
        CONF_CHALLENGE_THRESHOLD: _get_float_option(
            options,
            CONF_CHALLENGE_THRESHOLD,
            DEFAULT_CHALLENGE_THRESHOLD,
        ),
        CONF_CHALLENGE_CONFIRMATIONS: _get_int_option(
            options,
            CONF_CHALLENGE_CONFIRMATIONS,
            DEFAULT_CHALLENGE_CONFIRMATIONS,
        ),
        CONF_MINIMUM_POWER: _get_float_option(
            options,
            CONF_MINIMUM_POWER,
            DEFAULT_MINIMUM_POWER,
        ),
        CONF_RANKING_METHOD: _get_ranking_method(options),
    }


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

    configured_sources = entry.options.get(
        CONF_SOURCES,
        entry.data.get(CONF_SOURCES, []),
    )

    for source in configured_sources:
        normalized = _normalise_source(source)

        sources.append(
            {
                CONF_SOURCE_ID: normalized[CONF_SOURCE_ID],
                CONF_SOURCE_NAME: normalized[CONF_SOURCE_NAME],
                CONF_POWER_ENTITY: normalized[CONF_POWER_ENTITY],
                CONF_ENERGY_ENTITY: normalized[CONF_ENERGY_ENTITY],
                CONF_ENERGY_TYPE: normalized[CONF_ENERGY_TYPE],
                CONF_ICON: normalized[CONF_ICON],
            }
        )

    monitoring = _get_config_options(entry)

    connection.send_result(
        msg["id"],
        {
            "entry_id": entry.entry_id,
            "observation_interval": monitoring[CONF_OBSERVATION_INTERVAL],
            "observation_window": monitoring[CONF_OBSERVATION_WINDOW],
            "challenge_threshold": monitoring[CONF_CHALLENGE_THRESHOLD],
            "challenge_confirmations": monitoring[CONF_CHALLENGE_CONFIRMATIONS],
            "minimum_power": monitoring[CONF_MINIMUM_POWER],
            "ranking_method": monitoring[CONF_RANKING_METHOD],
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
            vol.In(OBSERVATION_INTERVAL_OPTIONS),
        ),
        vol.Required("observation_window"): vol.All(
            vol.Coerce(int),
            vol.Range(
                min=MIN_OBSERVATION_WINDOW,
                max=MAX_OBSERVATION_WINDOW,
            ),
        ),
        vol.Required("challenge_threshold"): vol.All(
            vol.Coerce(float),
            vol.Range(
                min=MIN_CHALLENGE_THRESHOLD,
                max=MAX_CHALLENGE_THRESHOLD,
            ),
        ),
        vol.Required("challenge_confirmations"): vol.All(
            vol.Coerce(int),
            vol.Range(
                min=MIN_CHALLENGE_CONFIRMATIONS,
                max=MAX_CHALLENGE_CONFIRMATIONS,
            ),
        ),
        vol.Required("minimum_power"): vol.All(
            vol.Coerce(float),
            vol.In(MINIMUM_POWER_OPTIONS),
        ),
        vol.Required("ranking_method"): vol.All(
            vol.Coerce(str),
            vol.In(RANKING_METHOD_OPTIONS),
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

        observation_interval = int(msg["observation_interval"])

        observation_window = int(msg["observation_window"])

        challenge_threshold = float(msg["challenge_threshold"])

        challenge_confirmations = int(msg["challenge_confirmations"])

        minimum_power = float(msg["minimum_power"])

        ranking_method = str(msg["ranking_method"])

    except (TypeError, ValueError, vol.Invalid) as err:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            str(err),
        )
        return

    if not (
        MIN_OBSERVATION_INTERVAL <= observation_interval <= MAX_OBSERVATION_INTERVAL
    ):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid observation interval.",
        )
        return

    if not (MIN_OBSERVATION_WINDOW <= observation_window <= MAX_OBSERVATION_WINDOW):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid observation window.",
        )
        return

    if not (MIN_CHALLENGE_THRESHOLD <= challenge_threshold <= MAX_CHALLENGE_THRESHOLD):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid challenge threshold.",
        )
        return

    if not (
        MIN_CHALLENGE_CONFIRMATIONS
        <= challenge_confirmations
        <= MAX_CHALLENGE_CONFIRMATIONS
    ):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid challenge confirmations.",
        )
        return

    if minimum_power not in MINIMUM_POWER_OPTIONS:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid minimum ranking power.",
        )
        return

    if ranking_method not in RANKING_METHOD_OPTIONS:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "Invalid ranking method.",
        )
        return

    options = dict(entry.options)

    options[CONF_SOURCES] = sources
    options[CONF_OBSERVATION_INTERVAL] = observation_interval
    options[CONF_OBSERVATION_WINDOW] = observation_window
    options[CONF_CHALLENGE_THRESHOLD] = challenge_threshold
    options[CONF_CHALLENGE_CONFIRMATIONS] = challenge_confirmations
    options[CONF_MINIMUM_POWER] = minimum_power
    options[CONF_RANKING_METHOD] = ranking_method

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
