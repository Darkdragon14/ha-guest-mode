
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
        self.content_type = "image/png"

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
    
    async def async_added_to_hass(self):
        """Called when entity is added to hass."""
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        """Update the QR code."""
        self._image_bytes = await self.hass.async_add_executor_job(self._generate_qr_code)

    async def async_image(self):
        """Return bytes of image."""
        if self._image_bytes is None:
            self._image_bytes = await self.hass.async_add_executor_job(self._generate_qr_code)
        return self._image_bytes

    def _generate_qr_code(self):
        """Generate the QR code for the last token."""
        conn = sqlite3.connect(self.hass.config.path(DATABASE))
        cursor = conn.cursor()
        cursor.execute("SELECT uid FROM tokens ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()

        if result:
            token = result[0]
            try:
                base_url = get_url(self.hass, prefer_external=True)
            except NoURLAvailableError:
                base_url = get_url(self.hass)
            guest_login_path = self.hass.data.get("get_path_to_login", "/guest-mode/login")
            full_url = f"{base_url}{guest_login_path}?token={token}"
            
            img = qrcode.make(full_url)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return buf.getvalue()
        
        return None
