from __future__ import annotations

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow

from .const import (
    CONF_SOURCES,
    DOMAIN,
)


class DynamicEnergyConfigFlow(
    ConfigFlow,
    domain=DOMAIN,
):
    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="Dynamic Energy",
                data={},
                options={
                    CONF_SOURCES: [],
                },
                description="success",
            )

        return self.async_show_form(
            step_id="user",
            data_schema=None,
        )
