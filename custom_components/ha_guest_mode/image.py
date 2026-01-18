
import logging
import sqlite3
import qrcode
import io
from homeassistant.components.image import ImageEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.network import get_url, NoURLAvailableError
from .const import DOMAIN, DATABASE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the image platform."""
    async_add_entities([GuestQRCodeImage(hass, config_entry)])

class GuestQRCodeImage(ImageEntity):
    """Representation of a QR code image for the last guest token."""

    def __init__(self, hass, config_entry):
        """Initialize the image entity."""
        super().__init__(hass)
        self.hass = hass
        self._config_entry = config_entry
        self._attr_name = "Guest QR Code"
        self._attr_unique_id = f"{DOMAIN}_guest_qr_code"
        self._attr_should_poll = True
        self._image_bytes = None
        self._token_attributes = {}
        self._attr_content_type = "image/png"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        integration = self.hass.data["integrations"].get(DOMAIN)
        version = None
        if integration and integration.manifest:
            version = integration.manifest.get("version")
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="HA Guest Mode",
            manufacturer="HA Guest Mode Community",
            model="Guest Access Control",
            sw_version=version or "unknown"
        )

    @property
    def state(self):
        return "Ready" if self._image_bytes else "No token"

    @property
    def extra_state_attributes(self):
        return self._token_attributes
    
    async def async_added_to_hass(self):
        """Called when entity is added to hass."""
        await self.async_update()
        self.async_write_ha_state()


    async def async_update(self):
        """Update the QR code and attributes."""
        token_row = await self.hass.async_add_executor_job(self._get_latest_token_row)
        self._token_attributes = {}
        self._image_bytes = None

        if token_row:
            user_name = await self._resolve_user_name(token_row.get("userId"), token_row.get("managed_user_name"))
            self._token_attributes = {
                "user": user_name,
                "start_date": token_row.get("start_date"),
                "end_date": token_row.get("end_date"),
                "first_used": token_row.get("first_used"),
                "last_used": token_row.get("last_used"),
                "times_used": token_row.get("times_used"),
                "usage_limit": token_row.get("usage_limit"),
            }

            uid = token_row.get("uid")
            if uid:
                self._image_bytes = await self.hass.async_add_executor_job(self._generate_qr_code, uid)

    async def async_image(self):
        """Return bytes of image."""
        if self._image_bytes is None:
            await self.async_update()
        return self._image_bytes
 
    def _get_latest_token_row(self):
        """Fetch the most recent token row from the database."""
        conn = sqlite3.connect(self.hass.config.path(DATABASE))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT userId, start_date, end_date, first_used, last_used, times_used, usage_limit, uid, managed_user_name
            FROM tokens
            ORDER BY id DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    async def _resolve_user_name(self, user_id, managed_user_name):
        """Resolve a human-friendly user label for attributes."""
        if not user_id:
            return managed_user_name

        user = await self.hass.auth.async_get_user(user_id)
        if user:
            return user.name

        return managed_user_name or user_id
 
    def _generate_qr_code(self, uid):
        """Generate the QR code for the provided token uid."""
        if not uid:
            return None

        try:
            base_url = get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            base_url = get_url(self.hass)
        guest_login_path = self.hass.data.get("get_path_to_login", "/guest-mode/login")
        full_url = f"{base_url}{guest_login_path}?token={uid}"
        
        img = qrcode.make(full_url)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

