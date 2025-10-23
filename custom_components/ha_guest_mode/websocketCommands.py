import logging
import sqlite3
from datetime import timedelta, datetime, timezone
from typing import Any
from collections import defaultdict
import voluptuous as vol
from contextlib import suppress
import jwt
import uuid
import json

from homeassistant.core import HomeAssistant
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers import config_validation as cv

from .const import DATABASE
from .lovelace_visibility import async_add_user_to_lovelace, async_remove_user_from_lovelace

LOGGER = logging.getLogger(__name__)


def _clean_dashboard_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if not normalized or normalized in cleaned:
            continue
        cleaned.append(normalized)
    return cleaned


def _deserialize_dashboards(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        decoded = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if isinstance(decoded, list):
        return _clean_dashboard_list(decoded)
    return []


def _collect_token_selections(row: Any) -> list[str]:
    data = dict(row) if not isinstance(row, dict) else row
    dashboards = _deserialize_dashboards(data.get("dashboards"))
    if dashboards:
        return dashboards
    dashboard = data.get("dashboard")
    if dashboard:
        return _clean_dashboard_list([dashboard])
    return []


def _selection_is_covered(selection: str, remaining: set[str]) -> bool:
    if selection in remaining:
        return True
    if "/" in selection:
        dashboard, _view = selection.split("/", 1)
        return dashboard in remaining
    return any(item.startswith(f"{selection}/") for item in remaining)


def _selections_to_remove(
    cursor: sqlite3.Cursor, user_id: str, token_id: int, selections: list[str]
) -> list[str]:
    if not selections or not user_id:
        return []
    cursor.execute(
        "SELECT dashboards, dashboard FROM tokens WHERE userId = ? AND id != ?",
        (user_id, token_id),
    )
    rows = cursor.fetchall()
    remaining: set[str] = set()
    for row in rows:
        remaining.update(_collect_token_selections(row))
    if not remaining:
        return selections
    return [selection for selection in selections if not _selection_is_covered(selection, remaining)]


async def _async_get_all_groups(hass: HomeAssistant):
    """Return all auth groups, compatible with multiple HA versions."""
    auth = hass.auth
    groups = []

    store = getattr(auth, "_store", None)
    if store is not None:
        getter = getattr(store, "async_get_groups", None)
        if getter is not None:
            groups = await getter()
            return list(groups)

    # Fallback to fetching known groups individually
    potential_ids = ("system-admin", "system-users", "system-read-only")
    getter = getattr(auth, "async_get_group", None)
    if getter is not None:
        for group_id in potential_ids:
            group = await getter(group_id)
            if group is not None:
                groups.append(group)

    return groups

@websocket_api.websocket_command({vol.Required("type"): "ha_guest_mode/list_users"})
@websocket_api.require_admin
@websocket_api.async_response
async def list_users(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    result = []
    now = dt_util.utcnow()

    conn = sqlite3.connect(hass.config.path(DATABASE))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tokens')
    token_rows = cursor.fetchall()

    async def remove_managed_user_if_needed(user_id: str, managed: bool) -> None:
        if not managed:
            return

        cursor.execute('SELECT COUNT(*) FROM tokens WHERE userId = ?', (user_id,))
        remaining = cursor.fetchone()[0]
        if remaining:
            return

        user = await hass.auth.async_get_user(user_id)
        if user and not user.system_generated:
            await hass.auth.async_remove_user(user)

    active_tokens = []
    for row in token_rows:
        token = dict(row)
        dashboards_list = _deserialize_dashboards(token.get("dashboards"))
        token["dashboards_list"] = dashboards_list
        is_never_expire = bool(token.get("is_never_expire"))
        end_date_str = token.get("end_date")

        if not is_never_expire and end_date_str:
            end_date = datetime.fromisoformat(end_date_str).replace(tzinfo=timezone.utc)

            if end_date < now:
                refresh_token_id = token.get("token_ha_id")
                if refresh_token_id:
                    with suppress(Exception):
                        refresh_token = hass.auth.async_get_refresh_token(refresh_token_id)
                        if refresh_token:
                            hass.auth.async_remove_refresh_token(refresh_token)

                selections = dashboards_list or _clean_dashboard_list([token.get("dashboard")])
                to_remove = _selections_to_remove(cursor, token.get("userId"), token["id"], selections)
                if to_remove:
                    with suppress(Exception):
                        await async_remove_user_from_lovelace(hass, to_remove, token.get("userId"))

                cursor.execute('DELETE FROM tokens WHERE id = ?', (token["id"],))
                await remove_managed_user_if_needed(token["userId"], bool(token.get("managed_user")))
                continue

        active_tokens.append(token)

    conn.commit()

    existing_users = {user.id: user for user in await hass.auth.async_get_users()}

    managed_tokens_missing_user = [
        token for token in active_tokens
        if token.get("managed_user") and token.get("userId") not in existing_users
    ]

    if managed_tokens_missing_user:
        available_groups = {group.id: group for group in await _async_get_all_groups(hass)}
        for token in managed_tokens_missing_user:
            stored_groups = token.get("managed_user_groups")
            group_ids: list[str] = []
            if stored_groups:
                try:
                    parsed = json.loads(stored_groups)
                    if isinstance(parsed, list):
                        group_ids = [gid for gid in parsed if gid in available_groups]
                except (ValueError, TypeError):
                    group_ids = []

            default_group = "system-users"
            if len(group_ids) > 1 and default_group in group_ids:
                group_ids = [gid for gid in group_ids if gid != default_group]
            if not group_ids and default_group in available_groups:
                group_ids.append(default_group)

            group_ids = list(dict.fromkeys(group_ids))  # preserve order, ensure unique

            user_name = token.get("managed_user_name") or token.get("token_name") or "Guest"
            new_user = await hass.auth.async_create_user(user_name, group_ids=group_ids or None)
            existing_users[new_user.id] = new_user

            token["userId"] = new_user.id
            token["managed_user_name"] = new_user.name

            stored_group_value = json.dumps(group_ids) if group_ids else None

            cursor.execute(
                "UPDATE tokens SET userId = ?, managed_user_name = ?, managed_user_groups = ? WHERE id = ?",
                (new_user.id, new_user.name, stored_group_value, token["id"]),
            )

            token["managed_user_groups"] = stored_group_value

        conn.commit()
        existing_users = {user.id: user for user in await hass.auth.async_get_users()}

    tokens_by_user = defaultdict(list)
    for token in active_tokens:
        tokens_by_user[token["userId"]].append(token)

    for user in existing_users.values():
        ha_username = next((cred.data.get("username") for cred in user.credentials if cred.auth_provider_type == "homeassistant"), None)

        tokens = []
        for token in tokens_by_user.get(user.id, []):
            is_never_expire = bool(token["is_never_expire"])
            remaining_seconds = None
            if not is_never_expire and token["end_date"]:
                remaining_seconds = int(
                    (datetime.fromisoformat(token["end_date"]).replace(tzinfo=timezone.utc) - now).total_seconds()
                )

            tokens.append(
                {
                    "id": token["id"],
                    "name": token["token_name"],
                    "type": TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
                    "end_date": token["end_date"],
                    "remaining": remaining_seconds,
                    "start_date": token["start_date"],
                    "isUsed": bool(token["token_ha"]),
                    "uid": token["uid"],
                    "isNeverExpire": is_never_expire,
                    "dashboard": token["dashboard"],
                    "dashboards": token.get("dashboards_list", []),
                    "first_used": token["first_used"],
                    "last_used": token["last_used"],
                    "times_used": token["times_used"] or 0,
                    "usage_limit": token["usage_limit"],
                }
            )

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


@websocket_api.websocket_command({vol.Required("type"): "ha_guest_mode/list_groups"})
@websocket_api.require_admin
@websocket_api.async_response
async def list_groups(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    groups = await _async_get_all_groups(hass)
    payload = [
        {
            "id": group.id,
            "name": group.name,
            "system_generated": group.system_generated,
        }
        for group in groups
    ]
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_guest_mode/create_token",
        vol.Optional("user_id"): str,
        vol.Required("name"): str, # token name
        vol.Optional("startDate"): int, # minutes
        vol.Optional("expirationDate"): int, # minutes
        vol.Optional("isNeverExpire", default=False): bool,
        vol.Optional("dashboard"): str,
        vol.Optional("dashboards"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("usage_limit"): vol.Any(vol.Coerce(int), None),
        vol.Optional("create_user", default=False): bool,
        vol.Optional("new_user_name"): str,
        vol.Optional("group_id"): str,
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
        dashboards_list = _clean_dashboard_list(msg.get("dashboards"))
        primary_dashboard = dashboards_list[0] if dashboards_list else (msg.get("dashboard") or "lovelace")
        usage_limit = msg.get("usage_limit")
        create_user = msg.get("create_user", False)
        user_id = msg.get("user_id")
        managed_user = False
        managed_user_name = None
        managed_user_groups = None

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

        if create_user:
            new_user_name = msg.get("new_user_name")
            if not new_user_name:
                connection.send_message(
                    websocket_api.error_message(
                        msg["id"],
                        websocket_api.const.ERR_INVALID_FORMAT,
                        "new_user_name is required when create_user is true",
                    )
                )
                return

            groups = await _async_get_all_groups(hass)
            default_group_id = next((group.id for group in groups if group.id == "system-users"), None)
            if default_group_id is None and groups:
                default_group_id = groups[0].id

            requested_group_id = msg.get("group_id")
            valid_group_ids = {group.id for group in groups}
            group_ids: list[str] = []

            if requested_group_id and requested_group_id in valid_group_ids:
                group_ids.append(requested_group_id)
            elif default_group_id:
                group_ids.append(default_group_id)

            try:
                user = await hass.auth.async_create_user(new_user_name, group_ids=group_ids or None)
            except ValueError as err:
                connection.send_message(
                    websocket_api.error_message(
                        msg["id"], websocket_api.const.ERR_UNKNOWN_ERROR, str(err)
                    )
                )
                return

            user_id = user.id
            managed_user = True
            managed_user_name = user.name
            managed_user_groups = json.dumps(group_ids) if group_ids else None

        if not user_id:
            connection.send_message(
                websocket_api.error_message(
                    msg["id"],
                    websocket_api.const.ERR_INVALID_FORMAT,
                    "user_id is required",
                )
            )
            return
        
        private_key = hass.data.get("private_key")
        if private_key is None:
            connection.send_message(msg["id"],  websocket_api.const.ERR_NOT_FOUND, "private key not found")
            return

        token_payload = {"id": msg["id"], "isNeverExpire": is_never_expire}
        if not is_never_expire:
            token_payload["startDate"] = startDate_iso
            token_payload["endDate"] = endDate_iso
        
        tokenGenerated = jwt.encode(token_payload, private_key, algorithm="RS256")

        dashboards_json = json.dumps(dashboards_list) if dashboards_list else None

        query = """
            INSERT INTO tokens (userId, token_name, start_date, end_date, token_ha_id, token_ha, token_ha_guest_mode, uid, is_never_expire, dashboard, dashboards, usage_limit, managed_user, managed_user_name, managed_user_groups)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn = sqlite3.connect(hass.config.path(DATABASE))
        try:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    user_id,
                    msg["name"],
                    startDate_iso,
                    endDate_iso,
                    "",
                    "",
                    tokenGenerated,
                    uid,
                    is_never_expire,
                    primary_dashboard,
                    dashboards_json,
                    usage_limit,
                    1 if managed_user else 0,
                    managed_user_name,
                    managed_user_groups,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        if dashboards_list:
            try:
                await async_add_user_to_lovelace(hass, dashboards_list, user_id)
            except Exception as err:
                LOGGER.warning("Failed to update Lovelace visibility for user %s: %s", user_id, err)

        await hass.services.async_call("homeassistant", "update_entity", {"entity_id": "image.guest_qr_code"}, blocking=True)

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
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT token_ha_id, userId, managed_user, dashboards, dashboard FROM tokens WHERE id = ?', (msg["token_id"],))
    token = cursor.fetchone()

    if token is None:
        conn.close()
        connection.send_result(msg["id"], False)
        return

    selections = _collect_token_selections(token)
    to_remove = _selections_to_remove(cursor, token["userId"], msg["token_id"], selections)
    if to_remove:
        try:
            await async_remove_user_from_lovelace(hass, to_remove, token["userId"])
        except Exception as err:
            LOGGER.warning("Failed to remove Lovelace visibility for user %s: %s", token["userId"], err)

    if token["token_ha_id"]:
        try:
            tokenHa = hass.auth.async_get_refresh_token(token["token_ha_id"])
            hass.auth.async_remove_refresh_token(tokenHa)
        except Exception:
            # Ignore if token is already removed from HA
            pass
    
    cursor.execute('DELETE FROM tokens WHERE id = ?', (msg["token_id"],))

    if token["managed_user"]:
        cursor.execute('SELECT COUNT(*) FROM tokens WHERE userId = ?', (token["userId"],))
        remaining = cursor.fetchone()[0]
        if not remaining:
            user = await hass.auth.async_get_user(token["userId"])
            if user and not user.system_generated:
                await hass.auth.async_remove_user(user)

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
