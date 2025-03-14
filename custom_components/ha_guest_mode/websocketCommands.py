import sqlite3
from datetime import timedelta, datetime, timezone
from typing import Any
import voluptuous as vol
import jwt
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util

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
            if  datetime.fromisoformat(token[4]).replace(tzinfo=timezone.utc) < now:
                if token[6] != "":
                    # @Todo maybe try catch here if token are already deleted
                    tokenHa = hass.auth.async_get_refresh_token(token[5])
                    hass.auth.async_remove_refresh_token(tokenHa)
                cursor.execute('DELETE FROM tokens WHERE id = ?', (token[0],))
                tokenLists.remove(token)
            if token[1] == user.id:
                tokens.append({
                    "id": token[0],
                    "name": token[2],
                    "type": TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
                    "end_date": token[4],
                    "remaining": int((datetime.fromisoformat(token[4]).replace(tzinfo=timezone.utc) - now).total_seconds()),
                    "start_date": token[3],
                    "isUsed": token[6] != "",
                    "uid": token[8]
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
        vol.Required("startDate"): int, # minutes
        vol.Required("expirationDate"): int, # minutes
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def create_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    try:
        now = datetime.now()
        startDate = now + timedelta(minutes=msg["startDate"])
        endDate = now + timedelta(minutes=msg["expirationDate"])
        uid = str(uuid.uuid4())
        
        private_key = hass.data.get("private_key")
        if private_key is None:
            connection.send_message(msg["id"],  websocket_api.const.ERR_NOT_FOUND, "private key not found")
        tokenGenerated = jwt.encode({"id": msg["id"],"startDate": startDate.isoformat(), "endDate": endDate.isoformat()}, private_key, algorithm="RS256")

        query = """
            INSERT INTO tokens (userId, token_name, start_date, end_date, token_ha_id, token_ha, token_ha_guest_mode, uid)
            values (?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn = sqlite3.connect(hass.config.path(DATABASE))
        cursor = conn.cursor()
        cursor.execute(query, (msg["user_id"], msg["name"], startDate.isoformat(), endDate.isoformat(), "", "", tokenGenerated, uid))
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
        tokenHa = hass.auth.async_get_refresh_token(token[0])
        hass.auth.async_remove_refresh_token(tokenHa)
    
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