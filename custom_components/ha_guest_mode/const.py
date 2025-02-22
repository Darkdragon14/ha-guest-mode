DOMAIN = "ha_guest_mode"

BASE_PATH = "custom_components/ha_guest_mode"
SCRIPT_JS = "ha-guest-mode.js"
DATABASE = f"{BASE_PATH}/ha_guest_mode.db"
KEY_FILE_PATH =  f"{BASE_PATH}/private_key.pem"
SOURCE_PATH_SCRIPT_JS = f"{BASE_PATH}/www/{SCRIPT_JS}"
DEST_PATH_SCRIPT_JS = "www/community/ha-guest-mode"

ICONS = [
    "mdi:lock","mdi:lock-open","mdi:key",
    "mdi:shield-lock","mdi:shield-key","mdi:shield-check",
    "mdi:account-lock","mdi:account","mdi:account-group",
    "mdi:account-key","mdi:key-variant","mdi:account-check",
    "mdi:account-lock-outline","mdi:account-circle","mdi:link",
    "mdi:link-variant","mdi:web","mdi:share-variant",
    "mdi:star","mdi:bell","mdi:email"
]

SHARING_MODES = ["link","email","sms","whatsapp","telegram","qr"]