from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN  # Assurez-vous que DOMAIN est défini dans const.py

class GuestModeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ha-guest-mode."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Guest Mode", data={})

        return self.async_show_form(step_id="user")
