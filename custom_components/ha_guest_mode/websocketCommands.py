import sqlite3
from datetime import timedelta, datetime, timezone
from typing import Any
import voluptuous as vol
from contextlib import suppress
import jwt
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DATABASE

@websocket_api.websocket_command({vol.Required("type"): "ha_guest_mode/list_users"})
@websocket_api.require_admin
@websocket_api.async_response
async def list_users(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    result = []
    now = dt_util.utcnow()

    conn = sqlite3.connect(hass.config.path(DATABASE))
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tokens')
    tokenLists = cursor.fetchall()    

    for user in await hass.auth.async_get_users():
        ha_username = next((cred.data.get("username") for cred in user.credentials if cred.auth_provider_type == "homeassistant"), None)

        tokens = []
        for token in tokenLists[:]:
            # Check for is_never_expire (index 9) and end_date (index 4)
            is_never_expire = token[9]
            
            # Handle expired tokens
            if not is_never_expire and token[4] and datetime.fromisoformat(token[4]).replace(tzinfo=timezone.utc) < now:
                if token[6] != "":
                    try:
                        tokenHa = hass.auth.async_get_refresh_token(token[5])
                        if tokenHa:
                            hass.auth.async_remove_refresh_token(tokenHa)
                    except Exception:
                        # Ignore if token is already removed from HA
                        pass
                cursor.execute('DELETE FROM tokens WHERE id = ?', (token[0],))
                tokenLists.remove(token)
                continue # Move to the next token

            if token[1] == user.id:
                remaining_seconds = None
                if not is_never_expire and token[4]:
                    remaining_seconds = int((datetime.fromisoformat(token[4]).replace(tzinfo=timezone.utc) - now).total_seconds())
                
                tokens.append({
                    "id": token[0],
                    "name": token[2],
                    "type": TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
                    "end_date": token[4],
                    "remaining": remaining_seconds,
                    "start_date": token[3],
                    "isUsed": token[6] != "",
                    "uid": token[8] if len(token) > 8 else None,
                    "isNeverExpire": is_never_expire,
                    "dashboard": token[10] if len(token) > 10 else None
                })

        result.append({
            "id": user.id,
            "username": ha_username,
            "name": user.name,
            "is_owner": user.is_owner,
            "is_active": user.is_active,
            "local_only": user.local_only,
            "system_generated": user.system_generated,
            "group_ids": [group.id for group in user.groups],
            "credentials": [{"type": c.auth_provider_type} for c in user.credentials],
            "tokens": tokens,
        })

    conn.commit()
    conn.close()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_guest_mode/create_token",
        vol.Required("user_id"): str,
        vol.Required("name"): str, # token name
        vol.Optional("startDate"): int, # minutes
        vol.Optional("expirationDate"): int, # minutes
        vol.Optional("isNeverExpire", default=False): bool,
        vol.Optional("dashboard"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def create_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    try:
        is_never_expire = msg.get("isNeverExpire", False)
        startDate_iso = None
        endDate_iso = None
        dashboard = msg.get("dashboard", "lovelace")

        if not is_never_expire:
            if "startDate" not in msg or "expirationDate" not in msg:
                connection.send_message(
                    websocket_api.error_message(
                        msg["id"],
                        websocket_api.const.ERR_INVALID_FORMAT,
                        "startDate and expirationDate are required when isNeverExpire is false",
                    )
                )
                return
            now = datetime.now()
            startDate = now + timedelta(minutes=msg["startDate"])
            endDate = now + timedelta(minutes=msg["expirationDate"])
            startDate_iso = startDate.isoformat()
            endDate_iso = endDate.isoformat()

        uid = str(uuid.uuid4())
        
        private_key = hass.data.get("private_key")
        if private_key is None:
            connection.send_message(msg["id"],  websocket_api.const.ERR_NOT_FOUND, "private key not found")
            return

        token_payload = {"id": msg["id"], "isNeverExpire": is_never_expire}
        if not is_never_expire:
            token_payload["startDate"] = startDate_iso
            token_payload["endDate"] = endDate_iso
        
        tokenGenerated = jwt.encode(token_payload, private_key, algorithm="RS256")

        query = """
            INSERT INTO tokens (userId, token_name, start_date, end_date, token_ha_id, token_ha, token_ha_guest_mode, uid, is_never_expire, dashboard)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn = sqlite3.connect(hass.config.path(DATABASE))
        cursor = conn.cursor()
        cursor.execute(query, (msg["user_id"], msg["name"], startDate_iso, endDate_iso, "", "", tokenGenerated, uid, is_never_expire, dashboard))
        conn.commit()
        conn.close()

    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], websocket_api.const.ERR_UNKNOWN_ERROR, str(err))
        )
        return

    connection.send_result(msg["id"], uid)

@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_guest_mode/delete_token",
        vol.Required("token_id"): int
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def delete_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    # @Todo add try catch to catch error with slqite
    conn = sqlite3.connect(hass.config.path(DATABASE))
    cursor = conn.cursor()
    cursor.execute('SELECT token_ha_id FROM tokens WHERE id = ?', (msg["token_id"],))
    token = cursor.fetchone()    

    if token[0] != "":
        try:
            tokenHa = hass.auth.async_get_refresh_token(token[0])
            hass.auth.async_remove_refresh_token(tokenHa)
        except Exception:
            # Ignore if token is already removed from HA
            pass
    
    cursor.execute('DELETE FROM tokens WHERE id = ?', (msg["token_id"],))
    conn.commit()
    conn.close()
    connection.send_result(msg["id"], True)

@websocket_api.websocket_command({vol.Required("type"): "ha_guest_mode/get_path_to_login"})
@websocket_api.require_admin
@websocket_api.async_response
async def get_path_to_login(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    connection.send_result(msg["id"], hass.data.get("get_path_to_login"))

@websocket_api.websocket_command({vol.Required("type"): "ha_guest_mode/get_urls"})
@websocket_api.require_admin
@websocket_api.async_response
async def get_urls(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get the internal, external, and cloud URLs."""
    internal_url = None
    external_url = None
    cloud_url = None
    with suppress(NoURLAvailableError):
        internal_url = get_url(
            hass, allow_internal=True, allow_external=False, allow_cloud=False
        )
    with suppress(NoURLAvailableError):
        external_url = get_url(
            hass, allow_internal=False, allow_external=True, prefer_external=True
        )

    connection.send_result(
        msg["id"],
        {
            "internal": internal_url,
            "external": external_url
        },
    )

@websocket_api.websocket_command({vol.Required("type"): "ha_guest_mode/get_panels"})
@websocket_api.require_admin
@websocket_api.async_response
async def get_panels(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    panels = hass.data.get("frontend_panels", {})
    result = []

    for url_path, panel in panels.items():
        result.append({
            "url_path": url_path,
            "title": panel.sidebar_title,
            "config": panel.config,
            "component_name": panel.component_name,
        })

    connection.send_result(msg["id"], result)

@websocket_api.websocket_command({vol.Required("type"): "ha_guest_mode/get_copy_link_mode"})
@websocket_api.require_admin
@websocket_api.async_response
async def get_copy_link_mode(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    connection.send_result(msg["id"], hass.data.get("copy_link_mode"))
