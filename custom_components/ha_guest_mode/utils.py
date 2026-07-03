from datetime import datetime, timezone
from inspect import isawaitable
import logging

from homeassistant.core import HomeAssistant
from homeassistant.const import STATE_ON
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN, QR_CODE_UNIQUE_ID


_LOGGER = logging.getLogger(__name__)
ACM_DOMAIN = "ha_access_control_manager"


def utcnow() -> datetime:
    """Return the current UTC time."""
    now = dt_util.utcnow()
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)

    return now.astimezone(timezone.utc)


def utcnow_isoformat() -> str:
    """Return the current UTC time as an ISO string."""
    return utcnow().isoformat()


def as_utc_datetime(value: datetime) -> datetime:
    """Normalize a datetime to UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)

    return value.astimezone(timezone.utc)


def parse_utc_datetime(value: str) -> datetime:
    """Parse a stored datetime and normalize it to UTC.

    Older tokens stored naive local datetimes. Treat those as Home Assistant's
    configured local timezone before converting them to UTC.
    """
    parsed = dt_util.parse_datetime(value) or datetime.fromisoformat(value)
    return as_utc_datetime(parsed)


def normalize_schedule_entity_id(value) -> str | None:
    """Normalize and validate an optional schedule entity id."""
    if value is None:
        return None

    entity_id = str(value).strip()
    if not entity_id:
        return None

    domain, separator, object_id = entity_id.partition(".")
    if domain != "schedule" or not separator or not object_id:
        raise ValueError("schedule_entity_id must be a schedule entity")

    return entity_id


def is_schedule_entity_active(hass: HomeAssistant, value) -> bool:
    """Return true only when the configured schedule exists and is on."""
    try:
        schedule_entity_id = normalize_schedule_entity_id(value)
    except ValueError:
        return False

    if schedule_entity_id is None:
        return True

    schedule_state = hass.states.get(schedule_entity_id)
    return schedule_state is not None and schedule_state.state == STATE_ON


async def async_update_qr_code_entity(hass: HomeAssistant) -> None:
    """Refresh the QR code image entity if it is registered."""
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("image", DOMAIN, QR_CODE_UNIQUE_ID)
    if entity_id is None:
        return

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": entity_id},
        blocking=True,
    )


async def async_sync_acm_dashboards(hass: HomeAssistant) -> None:
    """Ask Access Control Manager to sync dashboard view visibility if available."""
    acm_data = hass.data.get(ACM_DOMAIN)
    if not isinstance(acm_data, dict):
        return

    sync = acm_data.get("async_sync_group_dashboards_to_users")
    if not callable(sync):
        return

    try:
        result = sync(hass)
        if isawaitable(result):
            await result
    except Exception:
        _LOGGER.exception("Failed to synchronize Access Control Manager dashboards")
