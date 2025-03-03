import sqlite3
import os
import aiofiles

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import websocket_api
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.helpers import config_validation as cv

from .websocketCommands import list_users, create_token, delete_token, get_path_to_login
from .validateTokenView import ValidateTokenView
from .keyManager import KeyManager
from .const import DOMAIN, DATABASE, DEST_PATH_SCRIPT_JS, SOURCE_PATH_SCRIPT_JS, SCRIPT_JS

from .migrations import migration

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    websocket_api.async_register_command(hass, list_users)
    websocket_api.async_register_command(hass, create_token)
    websocket_api.async_register_command(hass, delete_token)
    websocket_api.async_register_command(hass, get_path_to_login)

    key_manager = KeyManager()
    await key_manager.load_or_generate_key()
    hass.data["private_key"] = key_manager.get_private_key()
    hass.data["public_key"] = key_manager.get_public_key()

    connection = sqlite3.connect(hass.config.path(DATABASE))
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        userId TEXT NOT NULL,
        token_name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        token_ha_id INTERGER,
        token_ha TEXT,
        token_ha_guest_mode TEXT NOT NULL
    )
    """)

    migration(cursor)

    connection.commit()
    connection.close()

    source_path = hass.config.path(SOURCE_PATH_SCRIPT_JS)
    dest_dir = hass.config.path(DEST_PATH_SCRIPT_JS)
    dest_path = os.path.join(dest_dir, SCRIPT_JS)

    try:
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        if os.path.exists(source_path):
            await async_copy_file(source_path, dest_path)

    except Exception as e:
        return False

    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up ha_guest_mode from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    hass.data["get_path_to_login"] = config_entry.options.get("login_path", config_entry.data.get("login_path", "/guest-mode/login"))

    tab_icon = config_entry.options.get("tab_icon", config_entry.data.get("tab_icon", "mdi:shield-key"))
    tab_name = config_entry.options.get("tab_name", config_entry.data.get("tab_name", "Guest"))
    path = config_entry.options.get("path_to_admin_ui", config_entry.data.get("path_to_admin_ui", "/guest-mode"))
    if path.startswith("/"):
        path = path[1:]

    panels = hass.data.get("frontend_panels", {})
    if path in panels:
        hass.components.frontend.async_remove_panel(path)

    hass.async_create_task(
        async_register_panel(
            hass,
            frontend_url_path=path,
            webcomponent_name="guest-mode-panel",
            module_url="/local/community/ha-guest-mode/ha-guest-mode.js",
            sidebar_title=tab_name,
            sidebar_icon=tab_icon,
            require_admin=True,
        )
    )

    hass.http.register_view(ValidateTokenView(hass))

    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    path = config_entry.options.get("path_to_admin_ui", config_entry.data.get("path_to_admin_ui", "/guest-mode"))
    if path.startswith("/"):
        path = path[1:]

    panels = hass.data.get("frontend_panels", {})
    if path in panels:
        hass.components.frontend.async_remove_panel(path)
    return True

async def async_copy_file(source_path, dest_path):
    async with aiofiles.open(source_path, 'rb') as src, aiofiles.open(dest_path, 'wb') as dst:
        while chunk := await src.read(1024):  # Adjust chunk size as needed
            await dst.write(chunk)