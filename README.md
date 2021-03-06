# home-assistant-exchange-calendar

Component that adds support for Exchange Calendars in [Home Assistant], based
on the [exchangelib] Python library.

## What to expect from this project

I wrote this Exchange Calendar integration for Home Assistant already in 2019. I published the
source code here because I noticed there are a few people asking for this feature from time to
time. If something can be improved and benefit others in a reasonable amount of time, feel free to
open a PR or an issue, but please be aware that I aim to spend as little time as possible on my
Home Assistant installation, and especially this project.

I'll keep it running until I eventually switch to a different email provider. I don't think it's
worth making it upstream (yet) but if you have time and want to make the effort, don't hesitate to
copy or take inspiration from this repository. I had a good experience when contributing to the
Home Assistant project a couple of years ago.

## How it works

The component adds a platform named `exchange_calendar`. It allows you to connect to an Exchange
server and adds a binary sensor that is activated when there is an ongoing event. The configuration
allows you to create multiple sensors that each match certain events based on their subject,
location or text body.

## Prerequisite

The component depends on the [exchangelib] Python library. You need to install it on your system at
least in version 3.2.0.

If you're using virtualenv and Home Assistant is installed in `/srv/homeassistant`, the
installation of the library could look like this:

```
# Go into the Home Assistant's installation directory
cd /srv/homeassistant

# Enter the project's virtual environment
source bin/activate

# Install the exchangelib library
pip3 install exchangelib

# or eventually upgrade it if it's already present but in an older version.
pip3 install exchangelib --upgrade

# Please be advised that this could interfere with other components if they
# also depend on exchangelib.
```

## Installation

The [developers documentation] explains very well how to create a custom component. Here is a
wrapup.

Create a folder named `custom_components` where you configuration is stored. For me, this is in
`.homeassistant`. Put the [exchange-calendar](./exchange-calendar) folder into `custom_components`.

The content of your configuraton directory could look like this:
```
<config-dir>/configuration.yaml
<config-dir>/.uuid
<config-dir>/secrets.yaml
<config-dir>/.storage/*
<config-dir>/home-assistant.log
<config-dir>/.HA_VERSION
<config-dir>/custom_components/exchange_calendar/__init__.py
<config-dir>/custom_components/exchange_calendar/calendar.py
```

## Configuration

The configuration is pretty much the same as for Home Assistant's [caldav] component.

### Basic Setup

The minimal setup requires you to add the following section to your
`configuration.yaml` file:
```
calendar:
  - platform: exchange_calendar
    server: "exchange.provider.com"
    username: myaccount@provider.com
    password: !secret exchange_password
```

This example generates a binary sensor for the calendar you have in your account. I haven't tested
what happens when you have more than one. This binary sensor will be *on* when there is an ongoing
event and *off* when there is none. Events that last a whole day are ignored. 

If you want to have such events taken into account, or if you wish to have sensors matching
specific events, continue reading.

### Custom calendars

You have the possibility to create multiple binary sensors for events that match certain
conditions. Those additional binary sensors don't ignore events that last a whole day.

```
calendar:
  - platform: exchange_calendar
    server: "exchange.provider.com"
    username: myaccount@provider.com
    password: !secret exchange_password
    calendars:
      - name: 'Agenda HomeOffice'
        search: 'HomeOffice'
      - name: 'Agenda FlatWarmup'
        search: 'WarmupFlat'
      - name: 'Agenda Guest'
        search: 'Guest'
```

This example creates three binary sensors named `Agenda HomeOffice`, `Agenda FlatWarmup` and
`Agenda Guest`. Those sensors will be *on* only if there is an ongoing event which's `Subject`,
`Location` or `Text` fields match the regular expression specified in search.

[caldav]: https://www.home-assistant.io/integrations/caldav/
[exchangelib]: https://pypi.org/project/exchangelib/
[Home Assistant]: https://www.home-assistant.io/
[virtualenv]: https://pypi.org/project/virtualenv/
[developers documentation]: https://developers.home-assistant.io/docs/creating_component_index/