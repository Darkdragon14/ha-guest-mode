import logging
import sqlite3
from contextlib import suppress
from typing import Callable

from homeassistant.const import STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DATABASE, DOMAIN
from .utils import is_access_entity_active, normalize_access_entity_id


_LOGGER = logging.getLogger(__name__)
# Keep the existing hass.data key so listeners survive integration upgrades safely.
_ACCESS_LISTENERS = "schedule_access_listeners"


def _get_access_listeners(hass: HomeAssistant) -> dict[str, Callable[[], None]]:
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault(_ACCESS_LISTENERS, {})


def _get_configured_access_entity_ids(hass: HomeAssistant) -> set[str]:
    access_entity_ids = set()
    for access_entity_id in _get_stored_access_entity_ids(hass):
        try:
            access_entity_ids.add(normalize_access_entity_id(access_entity_id))
        except ValueError:
            _LOGGER.warning("Ignoring invalid access entity id: %s", access_entity_id)

    return {entity_id for entity_id in access_entity_ids if entity_id}


def _get_stored_access_entity_ids(hass: HomeAssistant, only_used_tokens: bool = False) -> set[str]:
    conn = sqlite3.connect(hass.config.path(DATABASE))
    cursor = conn.cursor()
    query = """
        SELECT DISTINCT schedule_entity_id
        FROM tokens
        WHERE schedule_entity_id IS NOT NULL AND TRIM(schedule_entity_id) != ''
        """
    if only_used_tokens:
        query += " AND token_ha_id IS NOT NULL AND token_ha_id != ''"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return {access_entity_id for (access_entity_id,) in rows if access_entity_id}


async def async_revoke_access_tokens(hass: HomeAssistant, access_entity_id: str) -> None:
    """Revoke HA refresh tokens controlled by one access entity."""
    conn = sqlite3.connect(hass.config.path(DATABASE))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, token_ha_id
        FROM tokens
        WHERE schedule_entity_id = ? AND token_ha_id IS NOT NULL AND token_ha_id != ''
        """,
        (access_entity_id,),
    )
    tokens = cursor.fetchall()

    if not tokens:
        conn.close()
        return

    revoked_token_ids = []
    failed_token_ids = []
    for token in tokens:
        refresh_token_id = token["token_ha_id"]
        try:
            refresh_token = hass.auth.async_get_refresh_token(refresh_token_id)
            if refresh_token:
                hass.auth.async_remove_refresh_token(refresh_token)
            revoked_token_ids.append(token["id"])
        except Exception:
            failed_token_ids.append(token["id"])
            _LOGGER.exception(
                "Failed to revoke Guest Mode refresh token %s for access entity %s",
                refresh_token_id,
                access_entity_id,
            )

    if revoked_token_ids:
        cursor.executemany(
            "UPDATE tokens SET token_ha_id = ?, token_ha = ? WHERE id = ?",
            [("", "", token_id) for token_id in revoked_token_ids],
        )
        conn.commit()
    conn.close()

    _LOGGER.info(
        "Revoked %s Guest Mode token(s) because %s is not active",
        len(revoked_token_ids),
        access_entity_id,
    )
    if failed_token_ids:
        _LOGGER.warning(
            "Failed to revoke %s Guest Mode token(s) for %s; keeping token IDs for retry",
            len(failed_token_ids),
            access_entity_id,
        )


async def async_revoke_inactive_access_tokens(hass: HomeAssistant) -> None:
    """Revoke Guest Mode refresh tokens whose access entity is not on."""
    for access_entity_id in _get_stored_access_entity_ids(hass, only_used_tokens=True):
        if not is_access_entity_active(hass, access_entity_id):
            await async_revoke_access_tokens(hass, access_entity_id)


async def async_refresh_access_listeners(hass: HomeAssistant) -> None:
    """Synchronize state listeners with access entities used by tokens."""
    desired_entity_ids = _get_configured_access_entity_ids(hass)
    listeners = _get_access_listeners(hass)

    for entity_id in set(listeners) - desired_entity_ids:
        with suppress(Exception):
            listeners.pop(entity_id)()

    for entity_id in desired_entity_ids - set(listeners):

        @callback
        def _async_access_entity_changed(
            event: Event, tracked_entity_id: str = entity_id
        ) -> None:
            new_state = event.data.get("new_state")
            if new_state is not None and new_state.state == STATE_ON:
                return

            hass.async_create_task(async_revoke_access_tokens(hass, tracked_entity_id))

        listeners[entity_id] = async_track_state_change_event(
            hass, entity_id, _async_access_entity_changed
        )


async def async_setup_access_control(hass: HomeAssistant) -> None:
    """Set up access listeners and enforce current entity states."""
    await async_refresh_access_listeners(hass)
    await async_revoke_inactive_access_tokens(hass)


async def async_unload_access_control(hass: HomeAssistant) -> None:
    """Remove all access entity listeners."""
    listeners = _get_access_listeners(hass)
    for unsubscribe in list(listeners.values()):
        with suppress(Exception):
            unsubscribe()
    listeners.clear()
