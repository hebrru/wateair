# Home Assistant Custom Components : EasyCare for Waterair

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![release][release-badge]][release-url]

This is a Custom Components for [Home Assistant][home-assistant] to manage your [Waterair][waterair] Pool with the Easy-Care system.

This custom components aims to manage pool informations, lights and notifications (treatment, ph alert, ..). It will be completed by a lovelace card (work in progress).

**THIS IS A BETA VERSION** so let me know if it works or not ;)

## Installation

The simplest way to install this card is to add this repository to HACS. If you wish to install it manually, you may follow the instructions below.

### Upload to HA

Download source code zip file from this repository.
Copy `custom_components/easycare_waterair` into your Home Assistant `config/custom_components` directory.

### Restart HA
After installing the components using HACS or manually, you have to restart Home Assistant.
At this time, the component is ready to be used.

## Configuration
This integration is configured from the Home Assistant UI only.

Go to **Settings > Devices & services > Add integration**, search for
**EasyCare Waterair**, then enter your Waterair e-mail and password.

No `configuration.yaml` entry and no manual OAuth token are required anymore.
Once configured, you will see:

**8 new sensors:**
- easy_care_connection: a binary sensor for connection status
- easycare_pool_owner: a static sensor with owner name and address
- easycare_pool_detail: a static sensor with pool detail (type, volume, localization, custom_picture)
- easycare_pool_temperature: the current temperature
- easycare_pool_ph: the current Ph value
- easycare_pool_chlore: the current chlorine value
- easycare_pool_notification: the last notification (for chlorine treatement) or 'None' if all is well !
- easy_care_pool_treatment:  the last treatment (for ph treatement) or 'None' if all is well !

**2 lights:**
- easy_care_pool_spot: the light sensor for pool spot
- easy_care_pool_escalight: the light sensor for Escalight (if you have it)

**2 numbers:**
- easy_care_pool_spot_light_duration_in_hours: light duration for pool spot
- easy_care_pool_escalight_light_duration_in_hours: light duration for Escalight (if you have it)

You will also have sensor for the **pool AC1 module** and one **refresh button**:
- easycare_module_AC1-XXX: the easycare module to manage battery status (as attribute)
- easy_care_pool_refresh_data: refersh the data from Waterair

And one binary sensor (easycare_connection_sensor) to known if the connection is up

The refresh data is done every 30 minutes.

<!-- Badges -->
[release-badge]: https://img.shields.io/github/v/release/hebrru/wateair?style=flat-square
[downloads-badge]: https://img.shields.io/github/downloads/hebrru/wateair/total?style=flat-square

<!-- References -->
[home-assistant]: https://www.home-assistant.io/
[waterair]: https://www.waterair.com/
[hacs]: https://hacs.xyz
[release-url]: https://github.com/hebrru/wateair/releases
