from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_URL, PLATFORMS
from .coordinator import DynamicEnergyCoordinator
from .storage import DynamicEnergyStorage
from .websocket import async_register_websocket_commands

type DynamicEnergyConfigEntry = ConfigEntry[DynamicEnergyCoordinator]

_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"
_WEBSOCKET_REGISTERED = f"{DOMAIN}_websocket_registered"


async def async_setup(
    hass: HomeAssistant,
    config: dict,
) -> bool:
    if not hass.data.get(_WEBSOCKET_REGISTERED):
        async_register_websocket_commands(hass)
        hass.data[_WEBSOCKET_REGISTERED] = True

    return True


async def _async_register_frontend(
    hass: HomeAssistant,
) -> None:
    if hass.data.get(_FRONTEND_REGISTERED):
        return

    integration_path = Path(__file__).parent
    frontend_path = integration_path / "frontend" / "dynamic-energy-panel.js"

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL,
                str(frontend_path),
                cache_headers=False,
            )
        ]
    )

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=DOMAIN,
        webcomponent_name="dynamic-energy-panel",
        module_url=FRONTEND_URL,
        sidebar_title=None,
        sidebar_icon=None,
        require_admin=True,
        config_panel_domain=DOMAIN,
        embed_iframe=False,
    )

    hass.data[_FRONTEND_REGISTERED] = True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DynamicEnergyConfigEntry,
) -> bool:
    await _async_register_frontend(hass)

    storage = DynamicEnergyStorage(hass)

    coordinator = DynamicEnergyCoordinator(
        hass,
        entry,
        storage,
    )

    await coordinator.async_initialize()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: DynamicEnergyConfigEntry,
) -> bool:
    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
