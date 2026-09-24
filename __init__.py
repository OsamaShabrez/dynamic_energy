from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import (
    async_register_built_in_panel,
    async_remove_panel,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    FRONTEND_URL,
    PANEL_SIDEBAR_ICON,
    PANEL_SIDEBAR_TITLE,
    PANEL_URL_PATH,
    PLATFORMS,
)
from .coordinator import DynamicEnergyCoordinator
from .storage import DynamicEnergyStorage
from .websocket import async_register_websocket_commands

type DynamicEnergyConfigEntry = ConfigEntry[DynamicEnergyCoordinator]


async def async_setup(
    hass: HomeAssistant,
    config: dict,
) -> bool:
    """Set up Dynamic Energy."""

    async_register_websocket_commands(hass)

    frontend_path = Path(__file__).parent / "frontend" / "dynamic-energy-panel.js"

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL,
                str(frontend_path),
                False,
            )
        ]
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DynamicEnergyConfigEntry,
) -> bool:
    """Set up Dynamic Energy from a config entry."""

    storage = DynamicEnergyStorage(hass)

    coordinator = DynamicEnergyCoordinator(
        hass,
        entry,
        storage,
    )

    await coordinator.async_initialize()

    entry.runtime_data = coordinator

    async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_SIDEBAR_TITLE,
        sidebar_icon=PANEL_SIDEBAR_ICON,
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": "dynamic-energy-panel",
                "embed_iframe": False,
                "trust_external": False,
                "js_url": FRONTEND_URL,
            }
        },
        require_admin=True,
    )

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: DynamicEnergyConfigEntry,
) -> bool:
    """Unload Dynamic Energy."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        async_remove_panel(
            hass,
            PANEL_URL_PATH,
        )

    return unload_ok
