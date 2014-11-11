from datetime import datetime
try:
	from StringIO import StringIO
except:
	from io import StringIO
import pical
import glob
import os.path
import logging
logging.basicConfig()

def test_caldav_7_8_1():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			# <C:time-range start="20060104T000000Z" end="20060105T000000Z"/>
			cal = cal.time_range(time_range=[datetime(2006,1,4,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)])
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_1_")
			
			e = cal.clone()
			e.properties = []
			for name,value,params in cal.properties:
				if name == "VERSION":
					e.properties.append((name,value,params))
			e.children = []
			for c in cal.children:
				if c.name == "VTIMEZONE":
					e.children.append(c)
				elif c.name == "VEVENT":
					props = []
					for name,value,params in c.properties:
						if name in "SUMMARY UID DTSTART DTEND DURATION RRULE RDATE EXRULE EXDATE RECURRENCE-ID".split():
							props.append((name,value,params))
					c.properties = props
					e.children.append(c)
			
			if [c for c in e.children if c.name!="VTIMEZONE"]:
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_2():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			# <C:limit-recurrence-set start="20060103T000000Z" end="20060105T000000Z"/>
			cal = cal.time_range(recur=[datetime(2006,1,3,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)],
				time_range=[datetime(2006,1,3,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)],
				component="VEVENT")
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_2_")
			
			if [c for c in cal.children if c.name!="VTIMEZONE"]:
				assert cal==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_3():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			# <C:expand start="20060103T000000Z" end="20060105T000000Z"/>
			cal = cal.time_range(expand=[datetime(2006,1,3,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)],
				time_range=[datetime(2006,1,3,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)],
				component="VEVENT")
			cal = cal.clone(in_utc=True)
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_3_")
			
			if cal.children:
				assert cal==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_4():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			# <C:limit-freebusy-set start="20060102T000000Z" end="20060103T000000Z"/>
			cal = cal.time_range(time_range=[datetime(2006,1,2,tzinfo=pical.utc), datetime(2006,1,3,tzinfo=pical.utc)], component="VFREEBUSY")
			cal = cal.time_filter(fb_range=[datetime(2006,1,2,tzinfo=pical.utc), datetime(2006,1,3,tzinfo=pical.utc)])
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_4_")
			
			if [c for c in cal.children if c.name!="VTIMEZONE"]:
				assert cal==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_5():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			# <C:time-range start="20060106T100000Z" end="20060107T100000Z"/>
			cal = cal.time_range(alarm_range=[datetime(2006,1,6,10,0,0,tzinfo=pical.utc), datetime(2006,1,7,10,0,0,tzinfo=pical.utc)], component="VTODO")
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_5_")
			
			if [c for c in cal.children if c.name!="VTIMEZONE"]:
				assert cal==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_6():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			# <C:text-match collation="i;octet">DC6C50A017428C5216A2F1CD@example.com</C:text-match>
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_6_")
			
			e = cal.clone()
			e.children = []
			for comp in cal.children:
				if comp.name == "VTIMEZONE":
					e.children.append(comp)
				elif comp.name == "VEVENT" and comp.get("UID") == "DC6C50A017428C5216A2F1CD@example.com":
					e.children.append(comp)
			
			if [c for c in e.children if c.name!="VTIMEZONE"]:
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_7():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			# <C:prop-filter name="ATTENDEE"><C:text-match ...
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_7_")
			
			e = cal.clone()
			e.children = []
			for comp in cal.children:
				if comp.name == "VTIMEZONE":
					e.children.append(comp)
				elif comp.name == "VEVENT":
					for name,value,params in comp.properties:
						if (name=="ATTENDEE"
								and "mailto:lisa@example.com" == value.lower()
								and "NEEDS-ACTION" in dict(params).get("PARTSTAT",[])):
							e.children.append(comp)
							break
			
			if [c for c in e.children if c.name!="VTIMEZONE"]:
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2), f2

def test_caldav_7_8_8():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_8_")
			
			e = cal.clone()
			e.children = []
			for comp in cal.children:
				if comp.name == "VTIMEZONE":
					e.children.append(comp)
				elif comp.name == "VEVENT":
					e.children.append(comp)
			
			if [c for c in e.children if c.name!="VTIMEZONE"]:
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2), f2

def test_caldav_7_8_9():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			assert cal.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_9_")
			
			e = cal.clone()
			e.children = []
			for comp in cal.children:
				if comp.name == "VTIMEZONE":
					e.children.append(comp)
				elif (comp.name == "VTODO"
							and comp.get("COMPLETED") is None
							and "CANCELLED"!=comp.get("STATUS","").upper()):
						e.children.append(comp)
			
			if [c for c in e.children if c.name!="VTIMEZONE"]:
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2), f2

def test_caldav_7_10_1():
	# NOTE: VEVENT->VFREEBUSY conversion is not included in the library yet.
	dtstart = datetime(2006,1,4,14,tzinfo=pical.utc)
	dtend = datetime(2006,1,4,22,tzinfo=pical.utc)
	
	root = pical.Component.factory("VCALENDAR", {})
	root.parseProperty("VERSION","2.0",[])
	root.parseProperty("PRODID","-//Example Corp.//CalDAV Server//EN",[])
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for cal in pical.parse(open(f,"rb")):
			# <C:time-range start="20060104T140000Z" end="20060104T220000Z"/>
			cal = cal.time_range(expand=[dtstart,dtend]).clone(in_utc=True)
			root.freebusy_merge(cal)
	fb = root.children[0]
	fb.properties.append(("DTSTART", dtstart, []))
	fb.properties.append(("DTEND", dtend, []))
	root = root.time_filter(fb_range=[dtstart,dtend])
	
	f2 = "%s/rfc4791_7_10_1.ics" % os.path.dirname(__file__)
	if [c for c in root.children if c.name!="VTIMEZONE"]:
		assert root==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
	else:
		assert not os.path.exists(f2), f2

def test_parse():
	for f in glob.glob("%s/*.ics" % os.path.dirname(__file__)):
		for c in pical.parse(open(f,"rb")):
			fp = StringIO("\r\n".join(list(c.serialize())))
			pical.parse(fp)

def test_range():
	cal = pical.parse(open("%s/google_calendar_ex1.ics" % os.path.dirname(__file__),"rb"))[0]
	q = cal.time_range(expand=[datetime(2015,4,1,tzinfo=pical.utc), datetime(2015,6,1,tzinfo=pical.utc)])
	assert len([c for c in q.children if c.name=="VEVENT"])==10
	q = cal.time_range(time_range=[datetime(2015,4,1,tzinfo=pical.utc), datetime(2015,6,1,tzinfo=pical.utc)])
	assert len([c for c in q.children if c.name=="VEVENT"])==3

def test_eq():
	a = pical.parse(open("%s/google_calendar_ex1.ics" % os.path.dirname(__file__),"rb"))[0]
	b = pical.parse(open("%s/google_calendar_ex1.ics" % os.path.dirname(__file__),"rb"))[0]
	assert a==b, "__eq__ does not work"
	assert not a!=b, "__ne__ does not work"
	c = pical.parse(open("%s/rfc5545_3_4.ics" % os.path.dirname(__file__),"rb"))[0]
	assert a!=c, "__ne__ does not work"
	assert not a==c, "__eq__ does not work"

if __name__=="__main__":
	test_eq()
	test_parse()
	test_range()
	test_caldav_7_8_1()
	test_caldav_7_8_2()
	test_caldav_7_8_3()
	test_caldav_7_8_4()
	test_caldav_7_8_5()
	test_caldav_7_8_6()
	test_caldav_7_8_7()
	test_caldav_7_8_8()
	test_caldav_7_8_9()
	test_caldav_7_10_1()
