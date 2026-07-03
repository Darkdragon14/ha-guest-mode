import logging
import sqlite3
from contextlib import suppress
from typing import Callable

from homeassistant.const import STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DATABASE, DOMAIN
from .utils import is_schedule_entity_active, normalize_schedule_entity_id


_LOGGER = logging.getLogger(__name__)
_SCHEDULE_LISTENERS = "schedule_access_listeners"


def _get_schedule_listeners(hass: HomeAssistant) -> dict[str, Callable[[], None]]:
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault(_SCHEDULE_LISTENERS, {})


def _get_configured_schedule_entity_ids(hass: HomeAssistant) -> set[str]:
    schedule_entity_ids = set()
    for schedule_entity_id in _get_stored_schedule_entity_ids(hass):
        try:
            schedule_entity_ids.add(normalize_schedule_entity_id(schedule_entity_id))
        except ValueError:
            _LOGGER.warning("Ignoring invalid schedule entity id: %s", schedule_entity_id)

    return {entity_id for entity_id in schedule_entity_ids if entity_id}


def _get_stored_schedule_entity_ids(hass: HomeAssistant, only_used_tokens: bool = False) -> set[str]:
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
    return {schedule_entity_id for (schedule_entity_id,) in rows if schedule_entity_id}


async def async_revoke_schedule_tokens(hass: HomeAssistant, schedule_entity_id: str) -> None:
    """Revoke HA refresh tokens created by Guest Mode for one schedule."""
    conn = sqlite3.connect(hass.config.path(DATABASE))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, token_ha_id
        FROM tokens
        WHERE schedule_entity_id = ? AND token_ha_id IS NOT NULL AND token_ha_id != ''
        """,
        (schedule_entity_id,),
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
                "Failed to revoke Guest Mode refresh token %s for schedule %s",
                refresh_token_id,
                schedule_entity_id,
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
        schedule_entity_id,
    )
    if failed_token_ids:
        _LOGGER.warning(
            "Failed to revoke %s Guest Mode token(s) for %s; keeping token IDs for retry",
            len(failed_token_ids),
            schedule_entity_id,
        )


async def async_revoke_inactive_scheduled_tokens(hass: HomeAssistant) -> None:
    """Revoke Guest Mode refresh tokens for schedules that are not currently on."""
    for schedule_entity_id in _get_stored_schedule_entity_ids(hass, only_used_tokens=True):
        if not is_schedule_entity_active(hass, schedule_entity_id):
            await async_revoke_schedule_tokens(hass, schedule_entity_id)


async def async_refresh_schedule_listeners(hass: HomeAssistant) -> None:
    """Synchronize state listeners with the schedules currently used by tokens."""
    desired_entity_ids = _get_configured_schedule_entity_ids(hass)
    listeners = _get_schedule_listeners(hass)

    for entity_id in set(listeners) - desired_entity_ids:
        with suppress(Exception):
            listeners.pop(entity_id)()

    for entity_id in desired_entity_ids - set(listeners):

        @callback
        def _async_schedule_changed(
            event: Event, tracked_entity_id: str = entity_id
        ) -> None:
            new_state = event.data.get("new_state")
            if new_state is not None and new_state.state == STATE_ON:
                return

            hass.async_create_task(async_revoke_schedule_tokens(hass, tracked_entity_id))

        listeners[entity_id] = async_track_state_change_event(
            hass, entity_id, _async_schedule_changed
        )


async def async_setup_schedule_access(hass: HomeAssistant) -> None:
    """Set up schedule listeners and enforce current schedule states."""
    await async_refresh_schedule_listeners(hass)
    await async_revoke_inactive_scheduled_tokens(hass)


async def async_unload_schedule_access(hass: HomeAssistant) -> None:
    """Remove all schedule listeners."""
    listeners = _get_schedule_listeners(hass)
    for unsubscribe in list(listeners.values()):
        with suppress(Exception):
            unsubscribe()
    listeners.clear()
