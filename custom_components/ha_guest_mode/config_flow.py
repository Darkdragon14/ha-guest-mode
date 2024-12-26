import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .options_flow import OptionsFlowHandler
from .const import DOMAIN, ICONS

class GuestModeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ha-guest-mode."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        self.data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            self.data.update(user_input)
            return self.async_create_entry(title="Guest Mode", data=self.data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional("tab_icon", default="mdi:shield-key"): vol.In(ICONS),
                vol.Optional("tab_name", default="Guest"): str,
                vol.Optional("path_to_admin_ui", default="/guest-mode"): str,
                vol.Optional("login_path", default="/guest-mode/login"):str,
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)