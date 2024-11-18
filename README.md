# Guest Mode
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Hassfest](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hassfest.yml)
[![HACS Action](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hacs_action.yml/badge.svg)](https://github.com/Darkdragon14/ha-guest-mode/actions/workflows/hacs_action.yml)
[![release](https://img.shields.io/github/v/release/Darkdragon14/ha-guest-mode.svg)](https://github.com/Darkdragon14/ha-guest-mode/releases)
<!--Maybe later if the repo https://github.com/kcsoft/virtual-keys add one and can used-it[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)-->

Create login link for [Home Assistant](https://www.home-assistant.io/) that you can share with guests.

This is a fork of the original [Virtual-keys](https://github.com/kcsoft/virtual-keys) integration, designed for managing a "Guest Mode" in Home Assistant. It allows you to set up a dedicated mode for guest-friendly smart home interactions, ensuring a tailored experience while protecting personal configurations.
It's based on the code og [@kcsoft](https://github.com/kcsoft), I forked it and I work on it to have one repository and a start date. Other changes are coming

# Installation

## HACS installation

You need to install [HACS](https://hacs.xyz/) first.

* add "Custom repositories" to HACS, paste the URL of this repository and select "Integration" as category

* go to HACS -> Integrations, Explore and Download Repositories, search for "Guest Mode" and install it

* restart Home Assistant

* go in your settings -> devices and services, then add it

# Difference with the fork

You can choose a start date and an end date. Furthermore, the Home Assistant token is only created if the guest uses the link during the specified period.

If you want to know whether your guest has used the link, you can check the icon next to the token's name:

* Red: The link has not been used.
* Green: The link has been used, and the Home Assistant token has been created.

# Use case

I want to share an access with my friends that is valid for a limited time and that they can use to access specific entities in Home Assistant like the fron gate. The access is actually a link to my Home Assistant that can be opened in a browser.

To make this work, I need to make some optional and additional steps (before or after installing Ha Guest Mode):

* Create a new user in Home Assistant eg. "guest" (recommended)

* Create a new group eg. "guests" and add the user "guest" to it, and also the devices you want to give access to, eg "cover.front_gate", instructions [here](https://developers.home-assistant.io/blog/2019/03/11/user-permissions/) (optional)

* Create a new View (tab) in the default Lovelace UI and add the entities you want to give access to, eg. "cover.front_gate", set the visibility to only show to user "guest". (optional)

* Install [kiosk-mode](https://github.com/NemesisRE/kiosk-mode) and configure it set "kiosk" mode for user "guest" or [browser-mode](https://github.com/thomasloven/hass-browser_mod) to hide the sidebar for this user (optional)

This is it, you can now create access and share the link.

# Future improvements

* Add choice between start now and a start date :rocket:

* Add possibility to customize the tab name and path to access at admin ui :rocket:

* Add translate :rocket:

* Generate all path without absolute path :hammer_and_wrench:

* Improved error handling :hammer_and_wrench: