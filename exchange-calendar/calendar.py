"""Support for Exchange Calendar."""
import copy
from datetime import datetime, timedelta
import logging
import re

import voluptuous as vol

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    CalendarEntity,
    get_date,
    is_offset_reached,
)
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.util import Throttle, dt

_LOGGER = logging.getLogger(__name__)

CONF_CALENDARS = "calendars"
CONF_SEARCH = "search"
CONF_SERVER = "server"

OFFSET = "!!"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        # pylint: disable=no-value-for-parameter
        vol.Required(CONF_SERVER): cv.string,
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
        vol.Optional(CONF_CALENDARS, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_SEARCH): cv.string,
                    }
                )
            ],
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


def setup_platform(hass, config, add_entities, disc_info=None):
    """Set up the Exchange Calendar platform."""
    from exchangelib import Credentials, Account, Configuration, DELEGATE

    server = config[CONF_SERVER]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    credentials = Credentials(username, password)
    exconfig = Configuration(server=server, credentials=credentials, auth_type="NTLM")
    account = Account(username, config=exconfig, autodiscover=False, access_type=DELEGATE)

    calendar = account.calendar

    calendar_devices = []

    # Create additional calendars based on custom filtering rules
    for cust_calendar in config[CONF_CALENDARS]:
        name = cust_calendar[CONF_NAME]
        device_id = cust_calendar[CONF_NAME]
        entity_id = generate_entity_id(ENTITY_ID_FORMAT, device_id, hass=hass)
        calendar_devices.append(
            ExchangeCalendarEventDevice(
                name, calendar, entity_id, True, cust_calendar[CONF_SEARCH]
            )
        )

    add_entities(calendar_devices, True)


class ExchangeCalendarEventDevice(CalendarEntity):
    """A device for getting the next Task from a Exchange Calendar."""

    def __init__(self, name, calendar, entity_id, all_day=False, search=None):
        """Create the Exchange Calendar Event Device."""
        self.data = ExchangeCalendarData(calendar, all_day, search)
        self.entity_id = entity_id
        self._event = None
        self._name = name
        self._offset_reached = False

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return {"offset_reached": self._offset_reached}

    @property
    def event(self):
        """Return the next upcoming event."""
        return self._event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)

    def update(self):
        """Update event data."""
        self.data.update()
        event = copy.deepcopy(self.data.event)
        if event is None:
            self._event = event
            return
        self._offset_reached = is_offset_reached(event)
        self._event = event

from exchangelib import EWSDateTime

class ExchangeCalendarData:
    """Class to utilize the calendar dav client object to get next event."""

    def __init__(self, calendar, include_all_day, search):
        """Set up how we are going to search the Exchange calendar."""
        self.calendar = calendar
        self.include_all_day = include_all_day
        self.search = search
        self.event = None

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        # Get event list from the current calendar
        vevent_list = await hass.async_add_job(
            # (start__lt=end, end__gt=start):
            self.calendar.filter,
            start__range=(start_date, end_date),
        )
        event_list = []
        for vevent in vevent_list:
            uid = None
            if hasattr(vevent, "uid"):
                uid = vevent.uid

            data = {
                "uid": uid,
                "title": vevent.subject,
                "start": self.get_hass_date(vevent.start),
                "end": self.get_hass_date(vevent.end),
                "location": vevent.location,
                "description": vevent.text_body,
            }

            data["start"] = get_date(data["start"]).isoformat()
            data["end"] = get_date(data["end"]).isoformat()

            event_list.append(data)

        return event_list

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data."""
        # We have to retrieve the results for the whole day as the server
        # won't return events that have already started
        results = self.calendar.filter(
            start__lt=EWSDateTime.from_datetime(dt.now()),
            end__gt=EWSDateTime.from_datetime(dt.now()),
            end__lt=EWSDateTime.from_datetime(dt.now()+ timedelta(days=15))
        )

        vevent = next(
            (
                event
                for event in results
                if (
                    self.is_matching(event, self.search)
                    and (
                        not event.is_all_day
                        or self.include_all_day
                    )
                    and not self.is_over(event)
                )
            ),
            None,
        )

        # If no matching event could be found
        if vevent is None:
            _LOGGER.info(
                "No matching event found in the %d results for %s",
                results.count(),
                self.calendar.name,
            )
            self.event = None
            return

        # Populate the entity attributes with the event values
        self.event = {
            "summary": vevent.subject,
            "start": self.get_hass_date(vevent.start),
            "end": self.get_hass_date(vevent.end),
            "location": vevent.location,
            "description": vevent.text_body,
        }
        _LOGGER.info(self.event)


    @staticmethod
    def is_matching(event, search):
        """Return if the event matches the filter criteria."""
        if search is None:
            return True

        pattern = re.compile(search)
        return (
            hasattr(event, "subject")
            and not event.subject is None
            and pattern.match(event.subject)
            or hasattr(event, "location")
            and not event.location is None
            and pattern.match(event.location)
            or hasattr(event, "text_body")
            and not event.text_body is None
            and pattern.match(event.text_body)
        )

    @staticmethod
    def is_over(event):
        """Return if the event is over."""
        return dt.now() >= event.end

    @staticmethod
    def get_hass_date(obj):
        """Return if the event matches."""
        if isinstance(obj, datetime):
            return {"dateTime": obj.isoformat()}

        return {"date": obj.isoformat()}