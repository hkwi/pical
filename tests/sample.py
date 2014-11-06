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
		for c in pical.parse(open(f,"rb")):
			# <C:time-range start="20060104T000000Z" end="20060105T000000Z"/>
			u = c.time_range(time_range=[datetime(2006,1,4,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)])
			assert u.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_1_")
			if len([c for c in u.children if c.name=="VEVENT"]):
				e = u.clone()
				e.children = []
				e.properties = []
				for name,value,params in u.properties:
					if name == "VERSION":
						e.properties.append((name,value,params))
				for c in u.children:
					if c.name == "VEVENT":
						props = []
						for name,value,params in c.properties:
							if name in "SUMMARY UID DTSTART DTEND DURATION RRULE RDATE EXRULE EXDATE RECURRENCE-ID".split():
								props.append((name,value,params))
						c.properties = props
						e.children.append(c)
					elif c.name == "VTIMEZONE":
						e.children.append(c)
				
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_2():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for c in pical.parse(open(f,"rb")):
			# <C:limit-recurrence-set start="20060103T000000Z" end="20060105T000000Z"/>
			u = c.time_range(recur=[datetime(2006,1,3,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)], component="VEVENT")
			assert u.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_2_")
			if len([c for c in u.children if c.name=="VEVENT"]):
				assert u==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_3():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for c in pical.parse(open(f,"rb")):
			# <C:expand start="20060103T000000Z" end="20060105T000000Z"/>
			u = c.time_range(expand=[datetime(2006,1,3,tzinfo=pical.utc), datetime(2006,1,5,tzinfo=pical.utc)], component="VEVENT")
			assert u.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_3_")
			if len([c for c in u.children if c.name=="VEVENT"]):
				e = u.clone(in_utc=True)
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_4():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for c in pical.parse(open(f,"rb")):
			# <C:limit-freebusy-set start="20060102T000000Z" end="20060103T000000Z"/>
			u = c.time_range(time_range=[datetime(2006,1,2,tzinfo=pical.utc), datetime(2006,1,3,tzinfo=pical.utc)], component="VFREEBUSY")
			assert u.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_4_")
			if len([c for c in u.children if c.name=="VFREEBUSY"]):
				u = u.time_filter(fb_range=[datetime(2006,1,2,tzinfo=pical.utc), datetime(2006,1,3,tzinfo=pical.utc)])
				e = u.clone()
				e.children = []
				for c in u.children:
					if c.name == "VFREEBUSY":
						e.children.append(c)
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

def test_caldav_7_8_5():
	for f in glob.glob("%s/rfc4791_b_*.ics" % os.path.dirname(__file__)):
		for c in pical.parse(open(f,"rb")):
			# <C:time-range start="20060106T100000Z" end="20060107T100000Z"/>
			u = c.time_range(alarm_range=[datetime(2006,1,6,10,0,0,tzinfo=pical.utc), datetime(2006,1,7,10,0,0,tzinfo=pical.utc)], component="VTODO")
			assert u.name == "VCALENDAR"
			f2 = f.replace("_b_","_7_8_5_")
			if len([c for c in u.children if c.name=="VTODO"]):
				e = u.clone()
				e.children = []
				for c in u.children:
					if c.name == "VTODO":
						e.children.append(c)
				assert e==pical.parse(open(f2,"rb"))[0], "result %s mismatch" % f2
			else:
				assert not os.path.exists(f2)

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
