# Guest Mode
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA integration usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.ha_guest_mode.total)](https://analytics.home-assistant.io/custom_integrations.json)
[![Hassfest](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hassfest.yml)
[![HACS Action](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hacs_action.yml/badge.svg)](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hacs_action.yml)
[![release](https://img.shields.io/github/v/release/Darkdragon14/ha-guest-mode.svg)](https://github.com/Darkdragon14/ha-guest-mode/releases)
<!--Maybe later if the repo https://github.com/kcsoft/virtual-keys add one and can used-it[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)-->

Generate secure login links for [Home Assistant](https://www.home-assistant.io/) to share with your guests.

It's based on the code of [@kcsoft](https://github.com/kcsoft), I forked it and I work on it to have one repository and a start date. Other changes are coming

# Installation

## HACS installation

To install Guest Mode using [HACS](https://hacs.xyz/):

1. Add this repository as a custom repository in HACS:
   - Go to **HACS** → **Integrations** → **Add Custom Repository**.
   - Enter the URL of this repository and select **Integration** as the category.
2. Search for "Guest Mode" in HACS and install it.
3. Restart Home Assistant.
4. Go to **Settings** → **Devices & Services** → **Add Integration**.
5. Search for "Guest Mode" and select it.

## Customizable options

|Option Name|Description|required|default Value|
|---|---|---|---|
|**Tab Icon**|Icon for the Guest Mode tab, chosen from 23 MDI icons|No|`mdi:shield-key`|
|**Tab Name**|Name of the Guest Mode tab.  |No|`Guest`|
|**Path for Admin UI**|Custom URL path for accessing the admin interface|No|`/guest-mode`|
|**Login Path**|Custom URL path for guest to access the login page|No|`/guest-mode/login`|
|**Copy link directly (skips sharing)**|If checked, clicking the share button will copy the link directly to the clipboard instead of opening the native share dialog.|No|Unchecked|
|**Default User Name** (`default_user`)|Preselects the user when creating a token. This matches the Home Assistant user's **Name** field.|No|Empty|
|**Default Dashboard/View Path** (`default_dashboard`)|Preselects dashboard or dashboard view when creating a token. Use `dashboard` or `dashboard/view` (examples: `lovelace-guest`, `lovelace-guest/entry`) and do not include a leading slash.|No|Empty|


# Difference with the fork

In this version, all configurations are handled exclusively through the Home Assistant interface, allowing users to easily modify options as needed without manual edits.

You can set the link to be active immediately (default mode) or enable a date selector to specify a start date. Additionally, the Home Assistant token is generated only if the guest accesses the link within the defined time frame.

If you want to know whether your guest has used the link, you can check the icon next to the token's name:

* Red: The link has not been used.
* Green: The link has been used, and the Home Assistant token has been created.

# Use case

I want to share an access with my friends that is valid for a limited time and that they can use to access specific entities in Home Assistant like the fron gate. The access is actually a link to my Home Assistant that can be opened in a browser.

To make this work, I need to make some optional and additional steps (before or after installing Ha Guest Mode):

1. **Create a new user** in Home Assistant e.g. "guest" (recommended)

2. **Set permission**, create group e.g. "guests" and add this user this group, and also the devices you want to give access to, e.g. "cover.front_gate". See [User Permissions](https://developers.home-assistant.io/blog/2019/03/11/user-permissions/)

3. **Customize the interface** by creating a new View (tab) in the default Lovelace UI and add the entities you want to give access to, e.g. "cover.front_gate", set the visibility to only show to user "guest". (optional)

4. Use [Kiosk Mode](https://github.com/NemesisRE/kiosk-mode) or [Browser Mod](https://github.com/thomasloven/hass-browser_mod) to hide unnecessary UI elements for guests, like sidebar. (optional)

You can now generate a secure link to share with your guests.

# Services

This integration provides services that can be used in automations.

## Service: ha_guest_mode.create_token

Creates a new guest mode token.

| Parameter | Description | Required |
|---|---|---|
| `user_id` | The name of the user to create the token for. | Yes |
| `token_name` | The name of the token. | No |
| `expiration_duration` | The duration until the token expires (e.g., '02:00:00'). | No |
| `expiration_date` | The date when the token expires. | No |
| `start_date` | The date when the token becomes valid. | No |
| `dashboard` | The URL path of the desired dashboard (e.g., 'lovelace-guest'). Do not include the leading slash. | No |

**Note:** If neither `expiration_duration` nor `expiration_date` is provided, the token will never expire.

### Example

```yaml
- service: ha_guest_mode.create_token
  data:
    user_id: "guest"
    token_name: "My Guest Token"
    expiration_duration: "01:00:00" # 1 hour
```

# Entities

This integration creates the following entity:

| Entity ID | Name | Description |
|---|---|---|
| `image.guest_qr_code` | Guest QR Code | An image entity that displays a QR code for the most recently created guest token. The QR code contains the direct login URL for the guest. The state of the entity will be `Ready` if a token is available and a QR code has been generated, and `No token` otherwise. |

# Future improvements

* Removing seconds in UI or Using ha-date-range-picker :rocket:

* Fix timezone in display of the token :hammer_and_wrench:

* Adding a function to sanitize url for loginPath and path_to_admin_ui :hammer_and_wrench:

* Improving error handling and code maintainability. :hammer_and_wrench:

# Missing Translation

If you want this component to support another language, feel free to submit a PR or create an issue. If you open an issue, I’ll gladly handle the translation for you! :smile:

## Contributors

See [CONTRIBUTORS.md](./CONTRIBUTORS.md) for the full list of contributors.
