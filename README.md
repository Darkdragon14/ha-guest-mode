# Guest Mode
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA integration usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.ha_guest_mode.total)](https://analytics.home-assistant.io/custom_integrations.json)
[![Hassfest](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hassfest.yml)
[![HACS Action](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hacs_action.yml/badge.svg)](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hacs_action.yml)
[![release](https://img.shields.io/github/v/release/Darkdragon14/ha-guest-mode.svg)](https://github.com/Darkdragon14/ha-guest-mode/releases)
<!--Maybe later if the repo https://github.com/kcsoft/virtual-keys add one and can used-it[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)-->

Generate secure login links for [Home Assistant](https://www.home-assistant.io/) to share with your guests.

Guest Mode started as a fork of [Virtual Keys](https://github.com/kcsoft/virtual-keys) by [@kcsoft](https://github.com/kcsoft), but is now maintained as an independent Home Assistant integration with its own UI, configuration flow, release cycle, and roadmap.

# Installation

## HACS installation

[![Open your Home Assistant instance and open a repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Darkdragon14&repository=ha-guest-mode)

To install Guest Mode using [HACS](https://hacs.xyz/):

1. Click the button above, or add this repository manually as a custom repository in HACS:
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


# What Guest Mode provides

Guest Mode lets you create and manage temporary Home Assistant access links from a dedicated Home Assistant UI, without manually editing YAML or configuration files.

The integration provides:

* A redesigned admin interface to create, view, share, and manage guest access links.
* Temporary links with optional start date, expiration date, duration, and usage limit.
* Optional schedule-based access, allowing guest access only while a `schedule.*` entity is `on`.
* Native Home Assistant login using a selected guest user.
* Optional dashboard or dashboard view redirection after login.
* QR code generation for the latest guest link, exposed through the `image.guest_qr_code` entity.
* Share options, including native sharing or direct copy to clipboard depending on your configuration.
* Token status tracking, so you can see whether a guest link has already been used.
* Home Assistant services, allowing guest tokens to be created from automations.

For security, the Home Assistant long-lived access token is created only when the guest opens a valid link during the allowed time window, while the optional schedule is active, and before the usage limit is reached. When a configured schedule turns off, Guest Mode revokes the Home Assistant refresh token it created for that guest token. It does not disable or remove the Home Assistant user.

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
| `username` | The name of the user to create the token for. | Yes |
| `token_name` | The name of the token. | No |
| `expiration_duration` | The duration until the token expires (e.g., '02:00:00'). | No |
| `expiration_date` | The date when the token expires. | No |
| `start_date` | The date when the token becomes valid. | No |
| `dashboard` | The URL path of the desired dashboard (e.g., 'lovelace-guest'). Do not include the leading slash. | No |
| `schedule_entity_id` | Optional `schedule.*` entity. If set, guests can only access while this schedule is `on`; access tokens created by Guest Mode are revoked when it turns off. | No |

**Note:** If neither `expiration_duration` nor `expiration_date` is provided, the token will never expire.

### Example

```yaml
- service: ha_guest_mode.create_token
  data:
    username: "guest"
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
