# Guest Mode
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
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
|**Path for Admin UI**|Custom URL path for accessing the admin interface|No|`/guest-mode`


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

# Future improvements

* Removing seconds in UI or Using ha-date-range-picker :rocket:

* Improving error handling and code maintainability. :hammer_and_wrench:

# Missing Translation

If you want this component to support another language, feel free to submit a PR or create an issue. If you open an issue, I’ll gladly handle the translation for you! :smile: