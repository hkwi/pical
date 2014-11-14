pical
=====

``pical`` is a python icalendar library.

Supported features:

- parsing, building an ics file (icalendar version 2.0/rfc5545,rfc2445)
- querying for component with time-range (caldav/rfc4791)
- values will be accessible as python native types

Unsupported features:

- leap second support
- floating values with precision higher than `double`

Simple usage::

 from datetime import datetime
 import pical
 cals = pical.parse(open("tests/google_calendar_ex1.ics"))
 cal = cals[0]
 # subcomponents are stored in children
 for c in cal.children:
 	if c.name == "VEVENT":
 		print c["DTSTART"]

Time-range query example::

 from datetime import datetime
 import pical
 cals = pical.parse(open("tests/google_calendar_ex1.ics"))
 expcal = cals[0].time_range(expand=[datetime(2010,1,1,tzinfo=pical.utc), datetime.now(pical.utc)])
 for line in expcal.clone(in_utc=True).serialize():
 	print line

