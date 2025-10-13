import sqlite3
import os
import aiofiles
import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import websocket_api
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.helpers import config_validation as cv

from .websocketCommands import list_users, list_groups, create_token, delete_token, get_path_to_login, get_urls, get_panels, get_copy_link_mode
from .validateTokenView import ValidateTokenView
from .keyManager import KeyManager
from .const import DOMAIN, DATABASE, DEST_PATH_SCRIPT_JS, SOURCE_PATH_SCRIPT_JS, SCRIPT_JS
from .services import async_register_services

from .migrations import migration

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

def get_version():
    manifest_path = Path(__file__).parent / "manifest.json"
    try:
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f).get("version", "dev")
    except Exception:
        return "dev"

VERSION = get_version()

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await async_register_services(hass)

    websocket_api.async_register_command(hass, list_users)
    websocket_api.async_register_command(hass, list_groups)
    websocket_api.async_register_command(hass, create_token)
    websocket_api.async_register_command(hass, delete_token)
    websocket_api.async_register_command(hass, get_path_to_login)
    websocket_api.async_register_command(hass, get_urls)
    websocket_api.async_register_command(hass, get_panels)
    websocket_api.async_register_command(hass, get_copy_link_mode)

    key_manager = KeyManager()
    await key_manager.load_or_generate_key()
    hass.data["private_key"] = key_manager.get_private_key()
    hass.data["public_key"] = key_manager.get_public_key()

    connection = sqlite3.connect(hass.config.path(DATABASE))
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userId TEXT NOT NULL,
            token_name TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            token_ha_id TEXT,
            token_ha TEXT,
            token_ha_guest_mode TEXT NOT NULL,
            uid TEXT,
            is_never_expire BOOLEAN,
            dashboard TEXT,
            first_used TEXT,
            last_used TEXT,
            times_used INTEGER,
            usage_limit INTEGER,
            managed_user BOOLEAN DEFAULT 0,
            managed_user_name TEXT,
            managed_user_groups TEXT
        )
        """
    )

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

    hass.data["copy_link_mode"] = config_entry.options.get("copy_link_mode", config_entry.data.get("copy_link_mode", False))

    get_path_to_login = config_entry.options.get("login_path", config_entry.data.get("login_path", "/guest-mode/login"))
    if not get_path_to_login.startswith('/'):
        get_path_to_login = f"/{get_path_to_login}"
    hass.data["get_path_to_login"] = get_path_to_login

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
            module_url=f"/local/community/ha-guest-mode/ha-guest-mode.js?v={VERSION}",
            sidebar_title=tab_name,
            sidebar_icon=tab_icon,
            require_admin=True,
        )
    )

    hass.http.register_view(ValidateTokenView(hass))

    hass.async_create_task(hass.config_entries.async_forward_entry_setups(config_entry, ["image"]))

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
