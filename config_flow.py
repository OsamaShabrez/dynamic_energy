from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from .const import (
    CONF_OBSERVATION_INTERVAL,
    CONF_SOURCES,
    DEFAULT_OBSERVATION_INTERVAL,
    DOMAIN,
    MAX_OBSERVATION_INTERVAL,
    MIN_OBSERVATION_INTERVAL,
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
                    CONF_OBSERVATION_INTERVAL: int(
                        user_input[CONF_OBSERVATION_INTERVAL]
                    ),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_OBSERVATION_INTERVAL,
                    default=str(DEFAULT_OBSERVATION_INTERVAL),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=str(value),
                                label=f"{value} seconds",
                            )
                            for value in range(
                                MIN_OBSERVATION_INTERVAL,
                                MAX_OBSERVATION_INTERVAL + 1,
                                5,
                            )
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key="observation_interval",
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )
