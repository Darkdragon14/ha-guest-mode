import voluptuous as vol
from datetime import timedelta, datetime
import jwt
import uuid
import sqlite3

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN, DATABASE

async def async_create_token_service(hass: HomeAssistant, call: ServiceCall):
    translations = await async_get_translations(hass, hass.config.language, "config")

    username = call.data.get("username")
    token_name = call.data.get("token_name", "New Token")
    expiration_duration = call.data.get("expiration_duration")
    expiration_date = call.data.get("expiration_date")
    start_date = call.data.get("start_date")
    dashboard = call.data.get("dashboard", "lovelace")

    users = await hass.auth.async_get_users()
    user_id = None
    for u in users:
        if u.name == username:
            user_id = u.id
            break
    
    if user_id is None:
        raise vol.Invalid(translations.get("component.ha_guest_mode.config.error.user_not_found").format(username))

    if expiration_duration is not None and expiration_date is not None:
        raise vol.Invalid(translations.get("component.ha_guest_mode.config.error.expiration_exclusive"))

    if expiration_duration is None and expiration_date is None:
        is_never_expire = True
        startDate_iso = None
        endDate_iso = None
    else:
        is_never_expire = False
        now = datetime.now()
        
        if start_date:
            startDate = start_date
        else:
            startDate = now

        if expiration_duration:
            endDate = startDate + expiration_duration
        else:
            endDate = expiration_date
        
        startDate_iso = startDate.isoformat()
        endDate_iso = endDate.isoformat()

    uid = str(uuid.uuid4())
    private_key = hass.data.get("private_key")
    if private_key is None:
        return

    token_payload = {"id": uid, "isNeverExpire": is_never_expire}
    if not is_never_expire:
        token_payload["startDate"] = startDate_iso
        token_payload["endDate"] = endDate_iso
    
    tokenGenerated = jwt.encode(token_payload, private_key, algorithm="RS256")

    query = """
        INSERT INTO tokens (
            userId,
            token_name,
            start_date,
            end_date,
            token_ha_id,
            token_ha,
            token_ha_guest_mode,
            uid,
            is_never_expire,
            dashboard,
            usage_limit,
            managed_user,
            managed_user_name,
            managed_user_groups
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    conn = sqlite3.connect(hass.config.path(DATABASE))
    cursor = conn.cursor()
    cursor.execute(
        query,
        (
            user_id,
            token_name,
            startDate_iso,
            endDate_iso,
            "",
            "",
            tokenGenerated,
            uid,
            is_never_expire,
            dashboard,
            None,
            0,
            None,
            None,
        ),
    )
    conn.commit()
    conn.close()

    await hass.services.async_call("homeassistant", "update_entity", {"entity_id": "image.guest_qr_code"}, blocking=True)

async def async_register_services(hass: HomeAssistant):
    SERVICE_CREATE_TOKEN_SCHEMA = vol.Schema({
        vol.Required("username"): cv.string,
        vol.Optional("token_name"): cv.string,
        vol.Exclusive("expiration_duration", "expiration"): cv.time_period,
        vol.Exclusive("expiration_date", "expiration"): cv.datetime,
        vol.Optional("start_date"): cv.datetime,
        vol.Optional("dashboard"): cv.string,
    })

    async def async_handle_create_token(call: ServiceCall):
        await async_create_token_service(hass, call)

    hass.services.async_register(DOMAIN, "create_token", async_handle_create_token, schema=SERVICE_CREATE_TOKEN_SCHEMA)
