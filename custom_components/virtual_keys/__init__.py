from datetime import timedelta
from typing import Any
import voluptuous as vol
import jwt
from homeassistant.core import HomeAssistant
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.helpers.typing import ConfigType
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util

DOMAIN = "virtual_keys"


@websocket_api.websocket_command({vol.Required("type"): "virtual_keys/list_users"})
@websocket_api.require_admin
@websocket_api.async_response
async def list_users(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    result = []
    now = dt_util.utcnow()

    for user in await hass.auth.async_get_users():
        ha_username = next((cred.data.get("username") for cred in user.credentials if cred.auth_provider_type == "homeassistant"), None)

        tokens = []
        for token in list(user.refresh_tokens.values()):
            expiration_seconds = token.access_token_expiration.total_seconds()
            if (token.token_type == TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
                    and token.created_at + timedelta(seconds=expiration_seconds) < now):
                await hass.auth.async_remove_refresh_token(token)
            else:
                jwt_token = jwt.encode(
                    { "iss": token.id, "iat": now, "exp": now + token.access_token_expiration },
                    token.jwt_key,
                    algorithm="HS256",
                )

                tokens.append({
                    "id": token.id,
                    "name": token.client_name,
                    "jwt_token": jwt_token,
                    "type": token.token_type,
                    "expiration": expiration_seconds,
                    "remaining": round((token.created_at + timedelta(seconds=expiration_seconds) - now).total_seconds()),
                    "created_at": token.created_at.isoformat()
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

    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "virtual_keys/create_token",
        vol.Required("user_id"): str,
        vol.Required("name"): str, # token name
        vol.Required("minutes"): int, # minutes
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def create_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    users = await hass.auth.async_get_users()

    user = next((u for u in users if u.id == msg["user_id"]), None)
    if user is None:
        connection.send_message(
            websocket_api.error_message(msg["id"], websocket_api.const.ERR_NOT_FOUND, "User not found")
        )
        return

    try:
        refresh_token = await hass.auth.async_create_refresh_token(
            user,
            client_name=msg.get("name"),
            token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
            access_token_expiration=timedelta(minutes=msg["minutes"]),
        )
        access_token = hass.auth.async_create_access_token(refresh_token)
    except ValueError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], websocket_api.const.ERR_UNKNOWN_ERROR, str(err))
        )
        return

    connection.send_result(msg["id"], access_token)

@websocket_api.websocket_command(
    {
        vol.Required("type"): "virtual_keys/delete_token",
        vol.Required("token_id"): str
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def delete_token(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    for user in await hass.auth.async_get_users():
        for token in list(user.refresh_tokens.values()):
            if (token.id == msg.get("token_id")):
                hass.auth.async_remove_refresh_token(token)
                connection.send_result(msg["id"], True)
                return
    
    connection.send_result(msg["id"], False)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    websocket_api.async_register_command(hass, list_users)
    websocket_api.async_register_command(hass, create_token)
    websocket_api.async_register_command(hass, delete_token)

    return True
