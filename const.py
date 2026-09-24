from __future__ import annotations

DOMAIN = "dynamic_energy"
NAME = "Dynamic Energy"

CONF_SOURCES = "sources"
CONF_SOURCE_ID = "source_id"
CONF_SOURCE_NAME = "name"
CONF_POWER_ENTITY = "power_entity"
CONF_ENERGY_ENTITY = "energy_entity"
CONF_ENERGY_TYPE = "energy_type"
CONF_ICON = "icon"

CONF_OBSERVATION_INTERVAL = "observation_interval"

ENERGY_TYPE_MONTHLY = "monthly"
ENERGY_TYPE_CUMULATIVE = "cumulative"

DEFAULT_OBSERVATION_INTERVAL = 10
MIN_OBSERVATION_INTERVAL = 5
MAX_OBSERVATION_INTERVAL = 60

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"

PLATFORMS = ["sensor"]

SOURCE_FINGERPRINT_SEPARATOR = "|"

PANEL_URL_PATH = "dynamic-energy"
PANEL_SIDEBAR_TITLE = "Dynamic Energy"
PANEL_SIDEBAR_ICON = "mdi:lightning-bolt"

FRONTEND_URL = f"/api/{DOMAIN}/frontend/dynamic-energy-panel.js"

WS_TYPE_GET_CONFIG = f"{DOMAIN}/get_config"
WS_TYPE_SAVE_CONFIG = f"{DOMAIN}/save_config"
