import logging
from homeassistant import config_entries

_LOGGER = logging.getLogger(__name__)

class GuestModeConfigFlow(config_entries.ConfigFlow):
    """Flux de configuration pour l'intégration Guest Mode"""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Étape du flux de configuration pour la configuration initiale"""
        if user_input is None:
            # Aucune information n'est nécessaire, on ajoute directement l'intégration
            return self.async_create_entry(
                title="Guest Mode",
                data={},
            )
        
        # Si nécessaire, vous pouvez ajouter ici d'autres étapes ou logique
        return self.async_create_entry(
            title="Guest Mode",
            data={},
        )
